# ☕ Dawlo Café Management System

A full-stack **Café Management System** designed to manage daily café operations efficiently, including orders, tables, employees, suppliers, inventory, purchases, and payments.  
This project was developed as part of a **Database Systems course** and demonstrates proper **database design, normalization (3NF), relational schema mapping, and real-world system integration**.

---
👩‍💻 Authors

- Taima Nasser

- Lara Fuqaha

#### Computer Engineering – Database Systems Course
---

## 📌 Project Overview

The **Dawlo Café Management System** provides an integrated platform that connects front-end user interfaces with a well-structured relational database.  
It supports both **operational workflows** (orders, tables, payments) and **administrative management** (employees, suppliers, inventory, purchases).

The system is built to reflect real café scenarios and enforces data integrity using **primary keys, foreign keys, weak entities, and ternary relationships**.

---

## 🛠 Technologies Used

### Backend
- **Python (Flask)**  
  Used to implement server-side logic, routing, authentication, and database interaction.

- **MySQL**  
  Used as the relational database management system to store and manage all application data.

### Frontend
- **HTML5**  
  For structuring application pages.

- **CSS3**  
  For styling and layout.

- **Jinja2 (Flask Templates)**  
  For dynamic rendering of HTML pages using backend data.

### Database Design
- **ER Modeling**
- **Schema Mapping**
- **Third Normal Form (3NF)** normalization
- **Constraints (PK, FK, CHECK, UNIQUE)**

---

## 🧩 Main System Features

### Customer Management
- Add and manage customers
- Enforces unique phone numbers and emails

### Menu & Recipes
- Manage menu items and categories
- Link menu items to warehouse ingredients using recipes

### Orders
- Support for **dine-in** and **takeaway** orders
- Order status tracking (ordered, served, paid)
- Order-item linking with quantities and subtotals

### Table Management
- Physical table tracking with capacity
- Table sessions as weak entities
- Real-time table status (free, ordered, served, paid)

### Employees & Shifts
- Employee management with roles
- Shift tracking using time logs
- Employee–order relationship tracking

### Warehouse & Inventory
- Track stock levels and reorder thresholds
- Unit-based inventory management
- Low-stock monitoring

### Suppliers & Purchases
- Supplier management with activation status
- Supplier–item pricing and delivery tracking
- Purchase records with ternary relationships

### Stock Movement
- Automatic inventory updates
- Tracks stock changes due to orders and purchases

### Payments
- Cash and card payments
- Supports payments for orders and purchases
- Links payments to their respective transactions

---

## 🗂 Database Design Summary

- All relations are in **Third Normal Form (3NF)**
- Weak entities:
  - `Table_Session`
  - `Timelog`
- Ternary relationship:
  - `Purchase_Item_Supplier`
- Full referential integrity enforced using foreign keys
- Cascading deletes used where appropriate

---

## Academic Objectives Achieved

- ER-to-Relational Mapping

- Normalization to 3NF

- Use of weak entities and ternary relationships

- Real-world constraint enforcement

- Practical integration of database with application logic
---
## Conclusion

The Dawlo Café Management System demonstrates a complete and well-structured database-backed application, combining theoretical database design with practical implementation. It showcases effective schema design, normalization, and seamless integration with a functional user interface.
