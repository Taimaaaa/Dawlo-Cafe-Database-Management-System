# Taima 1222640, Lara 1220071

from flask import Flask, render_template, request, redirect, url_for
from db import get_db_connection
from datetime import datetime


app = Flask(__name__)

# ---------------------------
# helpers
# ---------------------------

def get_active_session(cur, table_id):
    """
    Returns the active session_start for a table (is_closed=0), or None.
    """
    cur.execute(
        """
        select session_start
        from Table_Session
        where table_id = %s and is_closed = 0
        order by session_start desc
        limit 1
        """,
        (table_id,)
    )
    row = cur.fetchone()
    return row["session_start"] if row else None


def ensure_active_session(cur, table_id):
    """
    Creates an active session for a table if none exists.
    Returns the active session_start.
    """
    active = get_active_session(cur, table_id)
    if active:
        return active

    # create new session now
    cur.execute(
        """
        insert into Table_Session (table_id, session_start, session_end, is_closed)
        values (%s, now(), null, 0)
        """,
        (table_id,)
    )
    # session_start is part of PK; easiest is to re-fetch it
    return get_active_session(cur, table_id)


def recompute_order_total(cur, order_id):
    cur.execute(
        """
        update Orders
        set total = (
            select ifnull(sum(subtotal), 0)
            from Order_Item
            where order_id = %s
        )
        where order_id = %s
        """,
        (order_id, order_id)
    )


def order_is_paid(cur, order_id):
    cur.execute("select order_status from Orders where order_id = %s", (order_id,))
    row = cur.fetchone()
    return (row and row["order_status"] == "paid")

TABLE_POSITIONS = {
    1:  (53, 12.84),
    2:  (53, 27.02),
    3:  (37.9, 44.66),
    4:  (27.71, 55.4),
    5:  (73.03, 13.05),
    6:  (73.03, 27),
    7:  (72.6, 44.3),
    8:  (72.6, 53.24),
    9:  (48.2, 68.28),
    10: (92.83, 13.4),
    11: (92.83, 26.8),
    12: (92.83, 38.41),
    13: (92.83, 49),
    14: (92.83, 59.68),
    15: (77.66, 74.3),
}



# ---------------------------
# routes
# ---------------------------

@app.route("/")
def home():
    return redirect(url_for("tables_dashboard"))



from datetime import datetime

@app.route("/tables")
def tables_dashboard():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("select table_id, capacity from Table_Entity order by table_id")
    tables = cur.fetchall()

    result = []

    for t in tables:
        table_id = int(t["table_id"])


        # active session
        cur.execute(
            """
            select session_start
            from Table_Session
            where table_id = %s and is_closed = 0
            order by session_start desc
            limit 1
            """,
            (table_id,)
        )
        row = cur.fetchone()
        active_start = row["session_start"] if row else None

        table_state = "free"
        latest_order = None
        can_close = False
        duration = None

        if active_start:
            # session duration
            diff = datetime.now() - active_start
            minutes = int(diff.total_seconds() // 60)
            duration = f"{minutes} min"

            # latest order
            cur.execute(
                """
                select order_id, order_status, total
                from Orders
                where table_id = %s and session_start = %s
                order by order_date desc
                limit 1
                """,
                (table_id, active_start)
            )
            latest_order = cur.fetchone()

            if not latest_order:
                table_state = "occupied_no_order_yet"
            else:
                st = latest_order["order_status"]
                if st == "ordered":
                    table_state = "ordered_waiting"
                elif st == "served":
                    table_state = "served_waiting_payment"
                elif st == "paid":
                    table_state = "paid_but_seated"

            # can close session only if all orders paid
            cur.execute(
                """
                select count(*) as cnt
                from Orders
                where table_id = %s
                  and session_start = %s
                  and order_status != 'paid'
                """,
                (table_id, active_start)
            )
            if cur.fetchone()["cnt"] == 0:
                can_close = True

        result.append({
            "table_id": table_id,
            "capacity": t["capacity"],
            "active_session_start": active_start,
            "session_duration": duration,
            "state": table_state,
            "latest_order": latest_order,
            "can_close": can_close
        })

    cur.close()
    conn.close()

    return render_template("tables.html", tables=result)

@app.route("/floorplan")
def floorplan_dashboard():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # 🔎 DEBUG (temporary)
    cur.execute("SELECT DATABASE() AS db")
    print("FLASK CONNECTED TO:", cur.fetchone()["db"])

    cur.execute("SELECT COUNT(*) AS cnt FROM Table_Entity")
    print("FLASK TABLE COUNT:", cur.fetchone()["cnt"])


    cur.execute("select table_id, capacity from Table_Entity order by table_id")
    tables = cur.fetchall()
    print("FLOORPLAN table_ids:", [int(t["table_id"]) for t in tables])


    result = []

    for t in tables:
        table_id = int(t["table_id"])
        active_start = get_active_session(cur, table_id)

        table_state = "free"
        latest_order = None

        if active_start:
            cur.execute(
                """
                select order_id, order_status, total, party_size
                from Orders
                where table_id = %s and session_start = %s
                order by order_date desc
                limit 1
                """,
                (table_id, active_start)
            )
            latest_order = cur.fetchone()

            if not latest_order:
                table_state = "occupied_no_order_yet"
            else:
                st = latest_order["order_status"]
                if st == "ordered":
                    table_state = "ordered_waiting"
                elif st == "served":
                    table_state = "served_waiting_payment"
                elif st == "paid":
                    table_state = "paid_but_seated"

        # 👇 THIS is where positioning belongs
        top, left = TABLE_POSITIONS.get(table_id, (50, 50))

        result.append({
            "table_id": table_id,
            "capacity": t["capacity"],
            "active_session_start": active_start,
            "state": table_state,
            "latest_order": latest_order,
            "pos_top": top,
            "pos_left": left
        })

    cur.close()
    conn.close()

    return render_template("floorplan.html", tables=result, full_width=True)



@app.route("/orders")
def orders_list():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute(
        """
        select
            o.order_id,
            o.order_date,
            o.order_status,
            o.total,
            o.order_type,
            o.table_id
        from Orders o
        order by o.order_date desc
        """
    )
    orders = cur.fetchall()

    cur.close()
    conn.close()
    return render_template("orders.html", orders=orders)


@app.route("/close_session", methods=["POST"])
def close_session():
    table_id = int(request.form["table_id"])
    session_start = request.form["session_start"]

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # safety: only close if all orders are paid
    cur.execute(
        """
        select count(*) as cnt
        from Orders
        where table_id = %s
          and session_start = %s
          and order_status != 'paid'
        """,
        (table_id, session_start)
    )

    if cur.fetchone()["cnt"] == 0:
        cur.execute(
            """
            update Table_Session
            set is_closed = 1,
                session_end = now()
            where table_id = %s and session_start = %s
            """,
            (table_id, session_start)
        )
        conn.commit()

    cur.close()
    conn.close()
    return redirect(request.referrer or url_for("floorplan_dashboard"))


@app.route("/start_order", methods=["GET", "POST"])
def start_order():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    error = None

    # ✅ ALWAYS define it (GET comes from floorplan click)
    selected_table = request.args.get("table_id", type=int)

    if request.method == "POST":
        customer_id = int(request.form["customer_id"])
        order_type = request.form["order_type"]

        table_id = None
        session_start = None
        party_size = 0

        if order_type == "dine_in":
            table_id = int(request.form["table_id"])
            party_size = int(request.form["party_size"])

            cur.execute(
                "select capacity from Table_Entity where table_id = %s",
                (table_id,)
            )
            capacity = cur.fetchone()["capacity"]

            session_start = ensure_active_session(cur, table_id)

            cur.execute(
                """
                select ifnull(sum(party_size), 0) as seated
                from Orders
                where table_id = %s
                  and session_start = %s
                  and order_status != 'paid'
                """,
                (table_id, session_start)
            )
            seated = cur.fetchone()["seated"]

            if seated + party_size > capacity:
                error = (
                    f"Table capacity exceeded. "
                    f"Capacity: {capacity}, "
                    f"Currently seated: {seated}"
                )
            else:
                cur.execute(
                    """
                    insert into Orders
                    (customer_id, table_id, session_start, order_date,
                     total, order_status, order_type, party_size)
                    values (%s, %s, %s, now(), 0, 'ordered', 'dine_in', %s)
                    """,
                    (customer_id, table_id, session_start, party_size)
                )
                conn.commit()
                order_id = cur.lastrowid
                cur.close()
                conn.close()
                return redirect(url_for("order_page", order_id=order_id))

        else:
            cur.execute(
                """
                insert into Orders
                (customer_id, order_date, total, order_status, order_type)
                values (%s, now(), 0, 'ordered', 'takeaway')
                """,
                (customer_id,)
            )
            conn.commit()
            order_id = cur.lastrowid
            cur.close()
            conn.close()
            return redirect(url_for("order_page", order_id=order_id))

    # GET request
    cur.execute("select customer_id, customer_name from Customer order by customer_name")
    customers = cur.fetchall()

    cur.execute("select table_id, capacity from Table_Entity order by table_id")
    tables = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "start_order.html",
        customers=customers,
        tables=tables,
        selected_table=selected_table,
        error=error
    )


@app.route("/order/<int:order_id>", methods=["GET", "POST"])
def order_page(order_id):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    message = None

    paid = order_is_paid(cur, order_id)

    if request.method == "POST":
        action = request.form.get("action")

        # -------- add item --------
        if action == "add" and not paid:
            menu_item_id = int(request.form["menu_item_id"])
            quantity = int(request.form["quantity"])

            cur.execute("select price from Menu_Item where item_id = %s", (menu_item_id,))
            price = cur.fetchone()["price"]
            add_subtotal = price * quantity

            cur.execute("""
                select quantity, subtotal
                from Order_Item
                where order_id = %s and menu_item_id = %s
            """, (order_id, menu_item_id))
            existing = cur.fetchone()

            if existing:
                cur.execute("""
                    update Order_Item
                    set quantity = quantity + %s,
                        subtotal = subtotal + %s
                    where order_id = %s and menu_item_id = %s
                """, (quantity, add_subtotal, order_id, menu_item_id))
            else:
                cur.execute("""
                    insert into Order_Item
                    (order_id, menu_item_id, quantity, subtotal, item_status)
                    values (%s, %s, %s, %s, 'ordered')
                """, (order_id, menu_item_id, quantity, add_subtotal))

            cur.execute("""
                select warehouse_item_id, quantity_required
                from Recipe
                where menu_item_id = %s
            """, (menu_item_id,))
            for ing in cur.fetchall():
                used = ing["quantity_required"] * quantity

                cur.execute(
                    "select stock_quantity from Warehouse_Item where item_id = %s",
                    (ing["warehouse_item_id"],)
                )
                if cur.fetchone()["stock_quantity"] < used:
                    conn.rollback()
                    cur.close()
                    conn.close()
                    return "Insufficient stock."

                cur.execute(
                    "update Warehouse_Item set stock_quantity = stock_quantity - %s where item_id = %s",
                    (used, ing["warehouse_item_id"])
                )
                cur.execute("""
                    insert into Stock_Movement
                    (movement_type, quantity_change, movement_date, warehouse_item_id, emp_id)
                    values ('sale', %s, now(), %s, 1)
                """, (-used, ing["warehouse_item_id"]))

            recompute_order_total(cur, order_id)
            conn.commit()
            return redirect(url_for("order_page", order_id=order_id))

        # -------- decrement item --------
        elif action == "decrement_item" and not paid:
            menu_item_id = int(request.form["menu_item_id"])

            cur.execute("""
                select quantity from Order_Item
                where order_id = %s and menu_item_id = %s
            """, (order_id, menu_item_id))
            row = cur.fetchone()

            if row:
                qty = row["quantity"]

                cur.execute("""
                    select warehouse_item_id, quantity_required
                    from Recipe
                    where menu_item_id = %s
                """, (menu_item_id,))
                for ing in cur.fetchall():
                    cur.execute("""
                        update Warehouse_Item
                        set stock_quantity = stock_quantity + %s
                        where item_id = %s
                    """, (ing["quantity_required"], ing["warehouse_item_id"]))

                if qty > 1:
                    cur.execute("""
                        update Order_Item
                        set quantity = quantity - 1,
                            subtotal = subtotal - (
                                select price from Menu_Item where item_id = %s
                            )
                        where order_id = %s and menu_item_id = %s
                    """, (menu_item_id, order_id, menu_item_id))
                else:
                    cur.execute("""
                        delete from Order_Item
                        where order_id = %s and menu_item_id = %s
                    """, (order_id, menu_item_id))

                recompute_order_total(cur, order_id)
                conn.commit()

            return redirect(url_for("order_page", order_id=order_id))

        # -------- delete entire order --------
        elif action == "delete_order" and not paid:
            cur.execute("delete from Order_Item where order_id = %s", (order_id,))
            cur.execute("delete from Orders where order_id = %s", (order_id,))
            conn.commit()
            return redirect(url_for("tables_dashboard"))

        # -------- mark served --------
        elif action == "served":
            cur.execute("update Orders set order_status = 'served' where order_id = %s", (order_id,))
            conn.commit()

        # -------- pay --------
        elif action == "pay":
            method = request.form["method"]

            cur.execute("""
                select total from Orders where order_id = %s
            """, (order_id,))
            total = cur.fetchone()["total"]

            cur.execute("""
                insert into Payment
                (payment_date, amount, method, payment_type, order_id)
                values (now(), %s, %s, 'order', %s)
            """, (total, method, order_id))

            cur.execute("update Orders set order_status = 'paid' where order_id = %s", (order_id,))
            conn.commit()
            message = "paid"

        # -------- assign employee --------
        elif action == "assign_employee":
            emp_id = int(request.form["emp_id"])

            cur.execute("""
                select 1 from Emp_Order
                where emp_id = %s and order_id = %s
            """, (emp_id, order_id))

            if not cur.fetchone():
                cur.execute(
                    "select position_title from Employee where emp_id = %s",
                    (emp_id,)
                )
                role = cur.fetchone()["position_title"]

                cur.execute("""
                    insert into Emp_Order (emp_id, order_id, role_in_order)
                    values (%s, %s, %s)
                """, (emp_id, order_id, role))
                conn.commit()

        # -------- remove employee --------
        elif action == "remove_employee":
            emp_id = int(request.form["emp_id"])
            cur.execute("""
                delete from Emp_Order
                where emp_id = %s and order_id = %s
            """, (emp_id, order_id))
            conn.commit()

    # ---------- page data ----------
    cur.execute("select * from Orders where order_id = %s", (order_id,))
    order = cur.fetchone()

    cur.execute("select item_id, item_name, price from Menu_Item where is_available = 1")
    menu_items = cur.fetchall()

    cur.execute("""
        select oi.menu_item_id, m.item_name, oi.quantity, oi.subtotal
        from Order_Item oi
        join Menu_Item m on oi.menu_item_id = m.item_id
        where oi.order_id = %s
    """, (order_id,))
    items = cur.fetchall()

    # employees currently clocked in
    cur.execute("""
        select distinct e.emp_id, e.emp_name, e.position_title
        from Employee e
        join Timelog t on e.emp_id = t.emp_id
        where e.is_active = 1 and t.shift_end is null
    """)
    available_employees = cur.fetchall()

    # assigned employees
    cur.execute("""
        select e.emp_id, e.emp_name, e.position_title
        from Emp_Order eo
        join Employee e on eo.emp_id = e.emp_id
        where eo.order_id = %s
    """, (order_id,))
    assigned_employees = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "order.html",
        order=order,
        menu_items=menu_items,
        items=items,
        message=message,
        paid=paid,
        available_employees=available_employees,
        assigned_employees=assigned_employees
    )

@app.route("/receipt/<int:order_id>")
def receipt(order_id):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute(
        """
        select o.order_id, o.order_date, o.total, o.order_type
        from Orders o
        where o.order_id = %s
        """,
        (order_id,)
    )
    order = cur.fetchone()

    cur.execute(
        """
        select m.item_name, oi.quantity, oi.subtotal
        from Order_Item oi
        join Menu_Item m on oi.menu_item_id = m.item_id
        where oi.order_id = %s
        """,
        (order_id,)
    )
    items = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("receipt.html", order=order, items=items)

@app.route("/employees")
def employees_dashboard():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # get all employees
    cur.execute("""
        SELECT emp_id, emp_name, position_title, is_active
        FROM Employee
        ORDER BY emp_id
    """)
    rows = cur.fetchall()

    employees = []

    for e in rows:
        emp_id = e["emp_id"]

        # 🔹 check if employee is currently clocked in
        cur.execute("""
            SELECT shift_start
            FROM Timelog
            WHERE emp_id = %s AND shift_end IS NULL
        """, (emp_id,))
        clocked_in = cur.fetchone() is not None

        employees.append({
            "emp_id": emp_id,
            "emp_name": e["emp_name"],
            "position_title": e["position_title"],
            "is_active": e["is_active"],
            "clocked_in": clocked_in
        })

    cur.close()
    conn.close()

    return render_template(
        "employees.html",
        employees=employees
    )


@app.route("/employees/toggle_active", methods=["POST"])
def toggle_employee_active():
    emp_id = int(request.form["emp_id"])

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute(
        """
        update Employee
        set is_active = 1 - is_active
        where emp_id = %s
        """,
        (emp_id,)
    )
    conn.commit()

    cur.close()
    conn.close()
    return redirect(url_for("employees_dashboard"))


# ---------------------------
# Clock In
# ---------------------------
@app.route("/employees/clock_in", methods=["POST"])
def clock_in():
    emp_id = int(request.form["emp_id"])

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # ensure employee is active
    cur.execute(
        "select is_active from Employee where emp_id = %s",
        (emp_id,)
    )
    emp = cur.fetchone()
    if not emp or emp["is_active"] == 0:
        cur.close()
        conn.close()
        return redirect(url_for("employees_dashboard"))

    # prevent double clock-in
    cur.execute(
        """
        select 1
        from Timelog
        where emp_id = %s and shift_end is null
        """,
        (emp_id,)
    )
    if cur.fetchone():
        cur.close()
        conn.close()
        return redirect(url_for("employees_dashboard"))

    # clock in
    cur.execute(
        """
        insert into Timelog (emp_id, shift_start, shift_end)
        values (%s, now(), null)
        """,
        (emp_id,)
    )

    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("employees_dashboard"))


# ---------------------------
# Clock Out
# ---------------------------
@app.route("/employees/clock_out", methods=["POST"])
def clock_out():
    emp_id = int(request.form["emp_id"])

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # clock out latest open shift
    cur.execute(
        """
        update Timelog
        set shift_end = now()
        where emp_id = %s
          and shift_end is null
        """,
        (emp_id,)
    )

    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("employees_dashboard"))


@app.route("/employees/<int:emp_id>/shifts")
def shift_history(emp_id):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # employee info
    cur.execute("""
        SELECT emp_name, position_title
        FROM Employee
        WHERE emp_id = %s
    """, (emp_id,))
    employee = cur.fetchone()

    if not employee:
        cur.close()
        conn.close()
        return "Employee not found", 404

    # shift history
    cur.execute("""
        SELECT shift_start, shift_end
        FROM Timelog
        WHERE emp_id = %s
        ORDER BY shift_start DESC
    """, (emp_id,))
    shifts = cur.fetchall()

    # compute duration (in minutes)
    for s in shifts:
        if s["shift_end"]:
            diff = s["shift_end"] - s["shift_start"]
            s["duration_min"] = int(diff.total_seconds() // 60)
        else:
            diff = datetime.now() - s["shift_start"]
            s["duration_min"] = int(diff.total_seconds() // 60)
            s["ongoing"] = True

    cur.close()
    conn.close()

    return render_template(
        "shift_history.html",
        employee=employee,
        shifts=shifts
    )
@app.route("/assign_employee", methods=["POST"])
def assign_employee():
    order_id = int(request.form["order_id"])
    emp_id = int(request.form["emp_id"])
    role = request.form["role"]

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # prevent duplicate assignment
    cur.execute(
        """
        SELECT 1 FROM Emp_Order
        WHERE emp_id = %s AND order_id = %s AND role_in_order = %s
        """,
        (emp_id, order_id, role)
    )

    if not cur.fetchone():
        cur.execute(
            """
            INSERT INTO Emp_Order (emp_id, order_id, role_in_order)
            VALUES (%s, %s, %s)
            """,
            (emp_id, order_id, role)
        )
        conn.commit()

    cur.close()
    conn.close()
    return redirect(url_for("order_page", order_id=order_id))


    
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template("500.html"), 500

if __name__ == "__main__":
    app.run(debug=False)
