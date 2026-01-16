# Taima 1222640, Lara 1220071

from flask import Flask, render_template, request, redirect, url_for, session, abort
from db import get_db_connection
from datetime import datetime
from functools import wraps


app = Flask(__name__)
app.secret_key = "dawlo-secret-key"   


# ---------------------------
# helpers
# ---------------------------

# for everyone
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "emp_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# manager only
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("position_title") != "manager":
            abort(403)
        return f(*args, **kwargs)
    return decorated

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
            select ifnull(sum(subtotal), 0)   -- returns order total = 0 if no active order items
            from Order_Item
            where order_id = %s
                and item_status != 'cancelled'
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

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        emp_id = request.form["emp_id"]

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT emp_id, emp_name, position_title
            FROM Employee
            WHERE emp_id = %s
        """, (emp_id,))

        emp = cur.fetchone()
        cur.close()
        conn.close()

        if emp:
            session["emp_id"] = emp["emp_id"]
            session["emp_name"] = emp["emp_name"]
            session["position_title"] = emp["position_title"]
            return redirect(url_for("home"))

        return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
def home():
    return redirect(url_for("tables_dashboard"))


from datetime import datetime

@app.route("/tables")
@login_required
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
                  and order_status IN ('pending', 'ordered', 'served')
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
@login_required
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

        # THIS is where positioning belongs
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
@login_required
def orders_list():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    field = request.args.get("field")
    search = request.args.get("search")

    allowed_fields = {
        "order_id": "order_id",
        "order_date": "DATE(order_date)",
        "order_status": "order_status",
        "order_type": "order_type",
        "table_id": "table_id",
        "total": "total"
    }

    if search:
        column = allowed_fields[field]

        cur.execute(
            f"""
            select order_id, order_date, total, order_status, order_type, table_id
            from Orders
            where {column} like %s
            order by order_id DESC
            """,
            (f"%{search}%",))
    else:
        cur.execute(
            """
            select order_id, order_date, total, order_status, order_type, table_id
            from Orders
            order by order_id DESC
            """
        )

    orders = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("orders.html", orders=orders)


@app.route("/close_session", methods=["POST"])
@login_required
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
          and order_status IN ('pending', 'ordered', 'served')
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
@login_required
def start_order():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    error = None

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

            cur.execute("""
                select party_size
                from Table_Session
                where table_id = %s
                and session_start = %s
                """, (table_id, session_start))

            row = cur.fetchone()
            seated = row["party_size"] or 0

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
                     total, order_status, order_type)
                    values (%s, %s, %s, now(), 0, 'pending', 'dine_in')
                    """,
                    (customer_id, table_id, session_start)
                )

                order_id = cur.lastrowid

                cur.execute("""
                    update Table_Session
                    set party_size = %s
                    where table_id = %s
                    and session_start = %s
                """, (seated + party_size, table_id, session_start))

                conn.commit()
                cur.close()
                conn.close()
                return redirect(url_for("order_page", order_id=order_id))

        else:
            cur.execute(
                """
                insert into Orders
                (customer_id, order_date, total, order_status, order_type)
                values (%s, now(), 0, 'pending', 'takeaway')
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
@login_required
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
                select quantity, subtotal, item_status
                from Order_Item
                where order_id = %s and menu_item_id = %s
            """, (order_id, menu_item_id))
            existing = cur.fetchone()

            if existing:
                if existing["item_status"] == "cancelled":  # if the item was ordered then cancelled then reordered again
                    cur.execute("""
                        update Order_Item
                        set quantity = %s,
                        subtotal = %s,
                        item_status = 'ordered'
                        where order_id = %s and menu_item_id = %s
                    """, (quantity, add_subtotal, order_id, menu_item_id))

                else: # if the item already exists in order increment quantity and subtotal
                    cur.execute("""
                        update Order_Item
                        set quantity = quantity + %s,
                            subtotal = subtotal + %s
                        where order_id = %s and menu_item_id = %s
                    """, (quantity, add_subtotal, order_id, menu_item_id))

            else: # if the item is ordered for the first time
                cur.execute("""
                    insert into Order_Item
                    (order_id, menu_item_id, quantity, subtotal)
                    values (%s, %s, %s, %s)
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

                emp_id = session["emp_id"]

                cur.execute("""
                    insert into Stock_Movement
                    (movement_type, quantity_change, movement_date, warehouse_item_id, emp_id)
                    values ('order', %s, now(), %s, %s)
                """, (-used, ing["warehouse_item_id"], emp_id))

            cur.execute(
                """ update Orders
                    set order_status = 'ordered'
                    where order_id = %s and order_status in ('pending', 'served')""",
                    (order_id,)
                )
            
            recompute_order_total(cur, order_id)
            conn.commit()
            return redirect(url_for("order_page", order_id=order_id))
        
        # -------- cancel item --------
        elif action == "cancel_item" and not paid:
            menu_item_id = int(request.form["menu_item_id"])

            # getting current item quantity 
            cur.execute("""
                select quantity
                from Order_Item
                where order_id = %s
                and menu_item_id = %s
                and item_status = 'ordered'
            """, (order_id, menu_item_id))

            row = cur.fetchone()

            if row and row["quantity"] > 0:
                qty = row["quantity"]  # current item quantity

                # restore stock for each ingredient
                cur.execute("""
                    select warehouse_item_id, quantity_required
                    from Recipe
                    where menu_item_id = %s
                """, (menu_item_id,))

                for ing in cur.fetchall():
                    restored = ing["quantity_required"] * qty  # we restore quantity required of ingredient * item quantity

                    # update warehouse stock
                    cur.execute("""
                        update Warehouse_Item
                        set stock_quantity = stock_quantity + %s
                        where item_id = %s
                    """, (restored, ing["warehouse_item_id"]))

                    emp_id = session["emp_id"]  # getting emp if of current logged in emp who currently makes stock changes

                    # insert change to stock movement
                    cur.execute("""
                        insert into Stock_Movement
                        (movement_type, quantity_change, movement_date, warehouse_item_id, emp_id)
                        values ('cancel_item', %s, now(), %s, %s)
                    """, (+restored, ing["warehouse_item_id"], emp_id))

                # marking item as cancelled 
                cur.execute("""
                    update Order_Item
                    set quantity = 0,
                        subtotal = 0,
                        item_status = 'cancelled'
                    where order_id = %s
                    and menu_item_id = %s
                """, (order_id, menu_item_id))

                # recompute order total
                recompute_order_total(cur, order_id)

                conn.commit()

            return redirect(url_for("order_page", order_id=order_id))


        # -------- decrement item --------
        elif action == "decrement_item" and not paid:
            menu_item_id = int(request.form["menu_item_id"])

            # retieving quantity od current itwm
            cur.execute("""
                select quantity from Order_Item
                where order_id = %s and menu_item_id = %s
            """, (order_id, menu_item_id))
            row = cur.fetchone()

            if row:
                qty = row["quantity"]

                # restoring stock for 1 unit
                cur.execute("""
                    select warehouse_item_id, quantity_required
                    from Recipe
                    where menu_item_id = %s
                """, (menu_item_id,))

                for ing in cur.fetchall():
                    restored = ing["quantity_required"]
                    
                    # updating warehouse stock
                    cur.execute("""
                        update Warehouse_Item
                        set stock_quantity = stock_quantity + %s
                        where item_id = %s
                    """, (restored, ing["warehouse_item_id"]))

                    emp_id = session["emp_id"]  # emp id of current logged in emp

                    # adding stock movement
                    cur.execute("""
                        insert into Stock_Movement
                        (movement_type, quantity_change, movement_date, warehouse_item_id, emp_id)
                        values ('cancel_item', %s, now(), %s, %s)
                    """, (restored, ing["warehouse_item_id"], emp_id))

                if qty > 1: # decrement 1
                    cur.execute("""
                        update Order_Item
                        set quantity = quantity - 1,
                            subtotal = subtotal - (select price from Menu_Item where item_id = %s)
                        where order_id = %s and menu_item_id = %s
                    """, (menu_item_id, order_id, menu_item_id))

                else: # cancel completely
                    cur.execute("""
                        update Order_Item
                        set quantity = 0,
                            subtotal = 0,
                            item_status = 'cancelled'
                        where order_id = %s and menu_item_id = %s
                    """, (order_id, menu_item_id))
    

                recompute_order_total(cur, order_id)
                conn.commit()

            return redirect(url_for("order_page", order_id=order_id))

        # ------- uncancel item --------
        elif action == "uncancel_item" and not paid:
            menu_item_id = int(request.form["menu_item_id"])

            # getting price
            cur.execute(
                "select price from Menu_Item where item_id = %s",
                (menu_item_id,))
            
            price = cur.fetchone()["price"]

            # deduct stock for 1 quantity bc we're reordering 1
            cur.execute("""
                select warehouse_item_id, quantity_required
                from Recipe
                where menu_item_id = %s
            """, (menu_item_id,))

            for ing in cur.fetchall():
                used = ing["quantity_required"]

                # check if stock is available
                cur.execute(
                    "select stock_quantity from Warehouse_Item where item_id = %s",
                    (ing["warehouse_item_id"],))
                
                if cur.fetchone()["stock_quantity"] < used:  # if the warehouse doesnt have enough stock cant order
                    conn.rollback()
                    return "Insufficient stock."

                # else update warehouse stock deducting
                cur.execute("""
                    update Warehouse_Item
                    set stock_quantity = stock_quantity - %s
                    where item_id = %s
                """, (used, ing["warehouse_item_id"]))

                emp_id = session["emp_id"]

                # inserting stock movement
                cur.execute("""
                    insert into Stock_Movement
                    (movement_type, quantity_change, movement_date, warehouse_item_id, emp_id)
                    values ('order', %s, now(), %s, %s)
                """, (-used, ing["warehouse_item_id"], emp_id))

            # restore the item with quantity 1 can later be incremented
            cur.execute("""
                update Order_Item
                set item_status = 'ordered',
                    quantity = 1,
                    subtotal = %s
                where order_id = %s
                and menu_item_id = %s
                and item_status = 'cancelled'
            """, (price, order_id, menu_item_id))

            # order state goes back to ordered
            cur.execute("""
                update Orders
                set order_status = 'ordered'
                where order_id = %s
            """, (order_id,))

            recompute_order_total(cur, order_id)
            conn.commit()

            return redirect(url_for("order_page", order_id=order_id))


        # -------- cancel whole order --------
        elif action == "cancel_order" and not paid:

            # get all items in the order except canceled ones
            cur.execute("""
                select menu_item_id, quantity
                from Order_Item
                where order_id = %s
                and item_status != 'cancelled'
                and quantity > 0
            """, (order_id,))

            items = cur.fetchall()

            for item in items:
                menu_item_id = item["menu_item_id"]
                qty = item["quantity"]

                # get recipe
                cur.execute("""
                    select warehouse_item_id, quantity_required
                    from Recipe
                    where menu_item_id = %s
                """, (menu_item_id,))

                for ing in cur.fetchall():
                    returned = ing["quantity_required"] * qty

                    # return stock to warehouse
                    cur.execute("""
                        update Warehouse_Item
                        set stock_quantity = stock_quantity + %s
                        where item_id = %s
                    """, (returned, ing["warehouse_item_id"]))

                    emp_id = session["emp_id"]

                    # insert stock movement
                    cur.execute("""
                        insert into Stock_Movement
                        (movement_type, quantity_change, movement_date, warehouse_item_id, emp_id)
                        values ('cancel_order', %s, now(), %s, %s)
                    """, (returned, ing["warehouse_item_id"], emp_id))

            # cancel all items
            cur.execute("""
                update Order_Item
                set item_status = 'cancelled',
                    quantity = 0,
                    subtotal = 0
                where order_id = %s
            """, (order_id,))

            # cancel the order itself
            cur.execute("""
                update Orders
                set order_status = 'cancelled',
                    total = 0
                where order_id = %s
            """, (order_id,))

            conn.commit()
            return redirect(url_for("tables_dashboard"))


        # -------- mark served --------
        elif action == "served":
            # mark whole order as served
            cur.execute("update Orders set order_status = 'served' where order_id = %s", (order_id,))

             # mark all active items as served
            cur.execute("""
                update Order_Item
                set item_status = 'served'
                where order_id = %s
                and item_status = 'ordered'
            """, (order_id,))

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

            return redirect(url_for("order_page", order_id=order_id))

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

        # -------- remove employee -----------------------------------------------------------------
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
        select oi.menu_item_id, m.item_name, oi.quantity, oi.subtotal, oi.item_status
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
@login_required
def receipt(order_id):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute(
        """
        select o.order_id, o.order_date, o.total, o.order_type
        from Orders o
        where o.order_id = %s and o.order_status != 'cancelled'
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
@login_required
@admin_required
def employees_dashboard():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    field = request.args.get("field")
    search = request.args.get("search")

    text_fields = {"emp_name": "emp_name",
                    "phone_number": "phone_number",
                    "position_title": "position_title",
                    "date_hired": "date_hired" }

    numeric_fields = { "emp_id": "emp_id",
                        "salary": "salary"}

    if search and field in text_fields:
        column = text_fields[field]

        cur.execute(f"""
            select *
            from Employee
            where {column} like %s
            order by emp_id
        """, (f"%{search}%",))

    elif search and field in numeric_fields:
        column = numeric_fields[field]

        cur.execute(f"""
            select *
            from Employee
            where {column} = %s
            order by emp_id
        """, (search,))

    else:
        cur.execute("""
            select *
            from Employee
            order by emp_id
        """)

    employees = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("employees.html", employees=employees, wide=True)


@app.route("/employees/toggle_active", methods=["POST"])
@login_required
@admin_required
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
@login_required
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
    return redirect(url_for("shift_history", emp_id=emp_id))


# Clock Out
@app.route("/employees/clock_out", methods=["POST"])
@login_required
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
    return redirect(url_for("shift_history", emp_id=emp_id))


@app.route("/employees/<int:emp_id>/shifts")
@login_required
def shift_history(emp_id):

    # authorization check
    if session.get("position_title") != "manager":
        # not a manager → can only see own shifts
        if emp_id != session.get("emp_id"):
            abort(403)

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
    
    # check if employee has an active shift
    cur.execute("""
        SELECT 1
        FROM Timelog
        WHERE emp_id = %s AND shift_end IS NULL
    """, (emp_id,))
    has_active_shift = cur.fetchone() is not None

    cur.close()
    conn.close()

    return render_template(
        "shift_history.html",
        employee=employee,
        shifts=shifts,
        has_active_shift=has_active_shift
    )

@app.route("/assign_employee", methods=["POST"])
@login_required
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

# adding new employees
@app.route("/employees/new", methods=["GET", "POST"])
@login_required
@admin_required
def add_employee():

    # only manager can add employees
    if session.get("position_title") != "manager":
        abort(403)

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form["emp_name"]
        salary = request.form["salary"]
        phone = request.form["phone_number"]
        position = request.form["position_title"]
        date_hired = request.form["date_hired"]

        cur.execute("""
            insert into Employee (emp_name, salary, phone_number, position_title, is_active, date_hired)
            values (%s, %s, %s, %s, 1, %s)
        """, (name, salary, phone, position, date_hired))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for("employees_dashboard"))

    cur.close()
    conn.close()

    return render_template("employee_form.html")

# updating employees info
@app.route("/employees/<int:emp_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_employee(emp_id):

    #  only manager
    if session.get("position_title") != "manager":
        abort(403)

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form["emp_name"]
        phone = request.form["phone_number"]
        position = request.form["position_title"]
        salary = request.form["salary"]
        date_hired = request.form["date_hired"]

        cur.execute("""
            update Employee
            set emp_name = %s,
                phone_number = %s,
                position_title = %s,
                salary = %s,
                date_hired = %s
            where emp_id = %s
        """, (name, phone, position, salary, date_hired, emp_id))

        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for("employees_dashboard"))

    # get employee info
    cur.execute("""
        select *
        from Employee
        where emp_id = %s
    """, (emp_id,))
    employee = cur.fetchone()

    cur.close()
    conn.close()

    if not employee:
        return "Employee not found", 404

    return render_template("employee_form.html", employee=employee)

# adding a new customer to the database 
@app.route("/customers/new", methods=["GET", "POST"])
@login_required
def add_customer():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    success = None

    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone_number"]
        email = request.form["email"]

        cur.execute("""
            INSERT INTO Customer (customer_name, phone_number, email)
            VALUES (%s, %s, %s)
        """, (name, phone, email))

        conn.commit()
        success = "Customer added successfully"

    cur.close()
    conn.close()

    return render_template("customer_form.html", customer=None, success=success)

@app.route("/customers")
@login_required
def customers_list():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    field = request.args.get("field")
    search = request.args.get("search")

    text_fields = {"customer_name": "customer_name",
                    "phone_number": "phone_number",
                    "email": "email"}

    numeric_fields = {"customer_id": "customer_id"}

    if search and field in text_fields:
        column = text_fields[field]

        cur.execute(f"""
            select *
            from Customer
            where {column} like %s
            order by customer_id
        """, (f"%{search}%",))

    elif search and field in numeric_fields:
        column = numeric_fields[field]

        cur.execute(f"""
            select *
            from Customer
            where {column} = %s
            order by customer_id
        """, (search,))

    else:
        cur.execute("""
            select *
            from Customer
            order by customer_id
        """)

    customers = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("customers.html", customers=customers)


# updating customer info
@app.route("/customers/<int:customer_id>/edit", methods=["GET", "POST"])
@login_required
def edit_customer(customer_id):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone_number"]
        email = request.form["email"]

        cur.execute("""
            UPDATE Customer
            SET customer_name = %s,
                phone_number = %s,
                email = %s
            WHERE customer_id = %s
        """, (name, phone, email, customer_id))

        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for("customers_list"))

    # GET
    cur.execute("""
        SELECT customer_name, phone_number, email
        FROM Customer
        WHERE customer_id = %s
    """, (customer_id,))
    customer = cur.fetchone()

    cur.close()
    conn.close()

    return render_template("customer_form.html", customer=customer)
    
@app.route("/payments")
@login_required
@admin_required
def payments():

    if session.get("position_title") != "manager":
        abort(403)

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    field = request.args.get("field")
    search = request.args.get("search")

    text_fields = {"payment_date": "DATE(payment_date)"}

    numeric_fields = {"order_id": "order_id",
                        "amount": "amount",
                        "payment_id": "payment_id"}

    if search and field in text_fields:
        column = text_fields[field]

        cur.execute(f"""
            select *
            from Payment
            where {column} = %s
            order by payment_id DESC
        """, (search,))

    elif search and field in numeric_fields:
        column = numeric_fields[field]
        cur.execute(f"""
            select *
            from Payment
            where {column} = %s
            order by payment_id DESC
        """, (search,))

    else:
        cur.execute("""
            select *
            from Payment
            order by payment_id DESC
        """)

    payments = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("payments.html", payments=payments)


@app.route("/menu")
@login_required
def menu_items():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    field = request.args.get("field")
    search = request.args.get("search")

    text_fields = {"item_name": "item_name", 
                   "category": "category",
                    "date_added": "DATE(date_added)" }

    numeric_fields = {"item_id": "item_id", 
                      "price": "price"}

    if search and field in text_fields:
        column = text_fields[field]
        cur.execute(f"""
            select *
            from Menu_Item
            where {column} like %s
            order by item_id
        """, (f"%{search}%",))

    elif search and field in numeric_fields:
        column = numeric_fields[field]
        cur.execute(f"""
            select *
            from Menu_Item
            where {column} = %s
            order by item_id
        """, (search,))

    # displaying all items
    else:
        cur.execute("""
            select *
            from Menu_Item
            order by item_id
        """)

    items = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("menu.html", items=items)

# updating menu items
@app.route("/menu/edit/<int:item_id>", methods=["GET", "POST"])
@login_required
@admin_required
def edit_menu_item(item_id):
    # restrict to managers
    if session.get("position_title") != "manager":
        abort(403)

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        item_name = request.form["item_name"]
        category = request.form["category"]
        price = request.form["price"]

        cur.execute("""
            update Menu_Item
            set item_name = %s,
                category = %s,
                price = %s
            where item_id = %s
        """, (item_name, category, price, item_id))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for("menu_items"))

    # GET request --> load item data
    cur.execute("""
        select *
        from Menu_Item
        where item_id = %s
    """, (item_id,))

    item = cur.fetchone()

    cur.close()
    conn.close()

    return render_template("edit_menu.html", item=item)

# making menu items available/unavailable
@app.route("/menu/toggle/<int:item_id>", methods=["POST"])
@login_required
@admin_required
def toggle_menu_item(item_id):
    # only managers
    if session.get("position_title") != "manager":
        abort(403)

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        update Menu_Item
        set is_available = 1 - is_available
        where item_id = %s
    """, (item_id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("menu_items"))

# adding new menu items
@app.route("/menu/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_menu_item():
    # restrict to managers
    if session.get("position_title") != "manager":
        abort(403)

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        item_name = request.form["item_name"]
        category = request.form["category"]
        price = request.form["price"]

        cur.execute("""
            insert into Menu_Item (item_name, category, price, date_added)
            values (%s, %s, %s, CURDATE())
        """, (item_name, category, price))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for("menu_items"))

    cur.close()
    conn.close()
    return render_template("edit_menu.html" ,item=None)

@app.route("/warehouse")
@login_required
def warehouse_items():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    field = request.args.get("field")
    search = request.args.get("search")

    text_fields = {"item_name": "item_name",
                    "unit_of_measure": "unit_of_measure"}

    numeric_fields = {"item_id": "item_id",
                        "stock_quantity": "stock_quantity",
                        "reorder_level": "reorder_level"}

    if search and field in text_fields:
        column = text_fields[field]

        cur.execute(f"""
            select *
            from Warehouse_Item
            where {column} like %s
            order by item_id
        """, (f"%{search}%",))

    elif search and field in numeric_fields:
        column = numeric_fields[field]
        cur.execute(f"""
            select *
            from Warehouse_Item
            where {column} = %s
            order by item_id
        """, (search,))

    else:
        cur.execute("""
            select *
            from Warehouse_Item
            order by item_id
        """)

    items = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("warehouse.html", items=items)

# adding new warehouse items
@app.route("/warehouse/new", methods=["GET", "POST"])
@login_required
@admin_required
def add_warehouse_item():

    if session.get("position_title") != "manager":
        abort(403)

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form["item_name"]
        stock = request.form["stock_quantity"]
        reorder = request.form["reorder_level"]
        unit = request.form["unit_of_measure"]

        cur.execute("""
            insert into Warehouse_Item (item_name, stock_quantity, reorder_level, unit_of_measure)
            values (%s, %s, %s, %s)
        """, (name, stock, reorder, unit))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for("warehouse_items"))

    cur.close()
    conn.close()
    return render_template("warehouse_form.html", item=None)

# editing warehouse items values
@app.route("/warehouse/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_warehouse_item(item_id):

    if session.get("position_title") != "manager":
        abort(403)

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form["item_name"]
        stock = request.form["stock_quantity"]
        reorder = request.form["reorder_level"]
        unit = request.form["unit_of_measure"]

        cur.execute("""
            update Warehouse_Item
            set item_name = %s,
                stock_quantity = %s,
                reorder_level = %s,
                unit_of_measure = %s
            where item_id = %s
        """, (name, stock, reorder, unit, item_id))

        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for("warehouse_items"))

    # GET item
    cur.execute("""
        select *
        from Warehouse_Item
        where item_id = %s
    """, (item_id,))
    item = cur.fetchone()

    cur.close()
    conn.close()

    if not item:
        return "Item not found", 404

    return render_template("warehouse_form.html", item=item)


@app.route("/stock_movements")
@login_required
@admin_required
def stock_movement():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    field = request.args.get("field")
    search = request.args.get("search")

    text_fields = {
        "movement_type": "sm.movement_type",
        "employee_name": "e.emp_name",
        "item_name": "w.item_name",
        "movement_date": "DATE(sm.movement_date)"
    }

    numeric_fields = {
        "movement_id": "sm.movement_id",
        "emp_id": "sm.emp_id",
        "warehouse_item_id": "sm.warehouse_item_id"
    }

    if search and field in text_fields:
        column = text_fields[field]
        cur.execute(f"""
            select sm.*, e.emp_name, w.item_name
            from Stock_Movement sm
            join Employee e ON sm.emp_id = e.emp_id
            join Warehouse_Item w ON sm.warehouse_item_id = w.item_id
            where {column} like %s
            order by sm.movement_id DESC
        """, (f"%{search}%",))

    elif search and field in numeric_fields:
        column = numeric_fields[field]
        cur.execute(f"""
            select sm.*, e.emp_name, w.item_name
            from Stock_Movement sm
            join Employee e ON sm.emp_id = e.emp_id
            join Warehouse_Item w ON sm.warehouse_item_id = w.item_id
            where {column} = %s
            order by sm.movement_id DESC
        """, (search,))

    else:
        cur.execute("""
            select sm.*, e.emp_name, w.item_name
            from Stock_Movement sm
            join Employee e ON sm.emp_id = e.emp_id
            join Warehouse_Item w ON sm.warehouse_item_id = w.item_id
            order by sm.movement_id DESC
        """)

    movements = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("stock_movement.html", movements=movements)


@app.route("/suppliers")
@login_required
@admin_required
def suppliers():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    field = request.args.get("field")
    search = request.args.get("search")

    text_fields = {
        "supplier_name": "supplier_name",
        "phone_number": "phone_number"}

    numeric_fields = {"supplier_id": "supplier_id"}

    if search and field in text_fields:
        column = text_fields[field]
        cur.execute(f"""
            select *
            from Supplier
            where {column} LIKE %s
            order by supplier_id
        """, (f"%{search}%",))

    elif search and field in numeric_fields:
        column = numeric_fields[field]
        cur.execute(f"""
            select *
            from Supplier
            where {column} = %s
            order by supplier_id
        """, (search,))

    else:
        cur.execute("""
            select *
            from Supplier
            order by supplier_id
        """)

    suppliers = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("suppliers.html", suppliers=suppliers)


@app.route("/suppliers/toggle_active", methods=["POST"])
@login_required
@admin_required
def toggle_supplier_active():
    supplier_id = int(request.form["supplier_id"])

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute(
        """
        update Supplier
        set is_active = 1 - is_active
        where supplier_id = %s
        """,
        (supplier_id,)
    )
    conn.commit()

    cur.close()
    conn.close()

    return redirect(url_for("suppliers"))


@app.route("/suppliers/new", methods=["GET", "POST"])
@login_required
@admin_required
def add_supplier():

    if session.get("position_title") != "manager":
        abort(403)

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form["supplier_name"]
        phone = request.form["phone_number"]

        cur.execute("""
            insert into Supplier (supplier_name, phone_number)
            values (%s, %s, %s)
        """, (name, phone))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for("suppliers"))

    cur.close()
    conn.close()
    return render_template("supplier_form.html", supplier=None)

@app.route("/suppliers/<int:supplier_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_supplier(supplier_id):

    if session.get("position_title") != "manager":
        abort(403)

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form["supplier_name"]
        phone = request.form["phone_number"]

        cur.execute("""
            update Supplier
            set supplier_name = %s,
                phone_number = %s,
            where supplier_id = %s
        """, (name, phone, supplier_id))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for("suppliers"))

    # GET supplier
    cur.execute("""
        select *
        from Supplier
        where supplier_id = %s
    """, (supplier_id,))
    supplier = cur.fetchone()

    cur.close()
    conn.close()

    if not supplier:
        return "Supplier not found", 404

    return render_template("supplier_form.html", supplier=supplier)


@app.route("/supplier_items")
@login_required
@admin_required
def supplier_items():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    field = request.args.get("field")
    search = request.args.get("search")

    text_fields = {
        "supplier_name": "s.supplier_name",
        "item_name": "w.item_name"}

    numeric_fields = {
        "supplier_id": "s.supplier_id",
        "warehouse_item_id": "w.item_id",
        "avg_delivery_days": "avg_delivery_days"}

    if search and field in text_fields:
        column = text_fields[field]
        cur.execute(f"""
            select s.supplier_id, s.supplier_name, w.item_id, w.item_name, w.unit_of_measure, 
                        si.unit_price, si.avg_delivery_days,  si.is_supplying
            from Supplier_Item si
            join Supplier s ON si.supplier_id = s.supplier_id
            join Warehouse_Item w ON si.warehouse_item_id = w.item_id
            where {column} like %s
            order by s.supplier_id, w.item_id
        """, (f"%{search}%",))

    elif search and field in numeric_fields:
        column = numeric_fields[field]
        cur.execute(f"""
            select s.supplier_id, s.supplier_name, w.item_id, w.item_name, w.unit_of_measure, 
                        si.unit_price, si.avg_delivery_days, si.is_supplying
            from Supplier_Item si
            join Supplier s ON si.supplier_id = s.supplier_id
            join Warehouse_Item w ON si.warehouse_item_id = w.item_id
            where {column} = %s
            order by s.supplier_id, w.item_id
        """, (search,))

    else:
        cur.execute("""
            select s.supplier_id, s.supplier_name, w.item_id, w.item_name, w.unit_of_measure, 
                        si.unit_price, si.avg_delivery_days, si.is_supplying
            from Supplier_Item si
            join Supplier s ON si.supplier_id = s.supplier_id
            join Warehouse_Item w ON si.warehouse_item_id = w.item_id
            order by s.supplier_id, w.item_id
        """)

    suppliers = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("supplier_items.html", suppliers=suppliers)

@app.route("/supplier_items/toggle_supplying", methods=["POST"])
@login_required
@admin_required
def toggle_supplier_item_supplying():

    supplier_id = int(request.form["supplier_id"])
    warehouse_item_id = int(request.form["warehouse_item_id"])

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        update Supplier_Item
        set is_supplying = 1 - is_supplying
        where supplier_id = %s and warehouse_item_id = %s
    """, (supplier_id, warehouse_item_id))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("supplier_items"))


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template("500.html"), 500

if __name__ == "__main__":
    app.run(debug=True)
