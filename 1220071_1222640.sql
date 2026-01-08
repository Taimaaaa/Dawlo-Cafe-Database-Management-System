drop database dawlo_phase3;
create database dawlo_phase3;
use dawlo_phase3;

create table Customer (
    customer_id int primary key auto_increment,
    customer_name varchar(64) not null,
    phone_number varchar(32),
    email varchar(64)
);

create table Menu_Item (
    item_id int primary key auto_increment,
    item_name varchar(64) not null unique,
    category varchar(32),   -- drink, dessert,...
    price real not null,
    is_available int default 1,   -- 1 available, 0 not available
    date_added date not null
);

-- items stored in the warehouse
create table Warehouse_Item (
    item_id int primary key auto_increment,
    item_name varchar(64) not null unique,
    stock_quantity real not null,
    reorder_level real not null,
    unit_of_measure varchar(32) not null
);

-- linking table between warehouse_item & menu_item
create table Recipe (
    menu_item_id int,
    warehouse_item_id int,
    quantity_required real not null,
    primary key (menu_item_id, warehouse_item_id),
    foreign key (menu_item_id) references Menu_Item (item_id),
    foreign key (warehouse_item_id) references Warehouse_Item (item_id)
);

-- physical tables in the cafe
create table Table_Entity (
    table_id int primary key auto_increment,
    capacity int not null
);

-- table session is a weak entity cannot exist without table entity
create table Table_Session (
    table_id int not null,
    session_start timestamp,
    session_end timestamp,     -- end time is unknown for active sessions
    is_closed int default 0,    -- 0 active session, 1 finished session
    primary key (table_id, session_start),
    foreign key (table_id) references Table_Entity (table_id) on delete cascade
);

create table Orders (
    order_id int primary key auto_increment,
    customer_id int not null,
    table_id int,
    party_size int,
    session_start timestamp,
    order_date timestamp not null,
    total real not null,
    order_status varchar(32) not null default 'ordered',
    order_type varchar(32) check (order_type in ('dine_in', 'takeaway')),
    foreign key (customer_id) references Customer (customer_id),
    foreign key (table_id, session_start) references Table_Session (table_id, session_start)
);

-- linking table between order & menu item
create table Order_Item (
    order_id int,
    menu_item_id int,
    quantity int not null,  -- quantity ordered of the menu item
    subtotal real not null,  -- = quantity * menu_item.price
    item_status varchar(32) not null default 'ordered',  -- preparing, ready, served, cancelled...
    primary key (order_id, menu_item_id),
    foreign key (order_id) references Orders (order_id),
    foreign key (menu_item_id) references Menu_Item (item_id)
);

create table Employee (
	emp_id int primary key auto_increment,
    emp_name varchar(64) not null,
    salary real not null,
    phone_number varchar(32),
    position_title varchar(32) not null,
    is_active int default 1  -- 1 emp currently working in the cafe, 0 emp resigned/terminated
);

-- timelog is a weak entity cannot exist without employee
create table Timelog (
	emp_id int,
	shift_start timestamp,
    shift_end timestamp,
    primary key (emp_id, shift_start),
    foreign key (emp_id) references Employee (emp_id) on delete cascade
);

-- linking table between employee & order
create table Emp_Order (
	emp_id int,
    order_id int,
    role_in_order varchar(32), -- employee's role in the order
    primary key (emp_id, order_id, role_in_order),
    foreign key (emp_id) references Employee (emp_id),
    foreign key (order_id) references Orders (order_id)
);

create table Purchase (
	purchase_id int primary key auto_increment,
    purchase_date date not null,
    payment_status varchar(32) not null,
    total_cost real not null,
    emp_id int not null,
    foreign key (emp_id) references Employee (emp_id)
);

create table Supplier (
	supplier_id int primary key auto_increment,
    supplier_name varchar (64) not null,
    phone_number varchar (32) 
);

-- a ternary relation: purchasing a warehouse item from a supplier
create table Purchase_Item_Supplier (
	purchase_id int,
    warehouse_item_id int,
    supplier_id int,
    quantity real not null,
    unit_cost real not null,
    primary key (purchase_id, warehouse_item_id, supplier_id),
    foreign key (purchase_id) references Purchase (purchase_id),
    foreign key (warehouse_item_id) references Warehouse_Item (item_id),
    foreign key (supplier_id) references Supplier (supplier_id)
);

create table Supplier_Item (
	supplier_id int,
    warehouse_item_id int,
    unit_price real not null,
    avg_delivery_days int,
    primary key (supplier_id, warehouse_item_id),
    foreign key (supplier_id) references Supplier (supplier_id),
    foreign key (warehouse_item_id) references Warehouse_Item (item_id)
);

create table Stock_Movement (
	movement_id int primary key auto_increment,
    movement_type varchar (32) not null check (movement_type in ('purchase', 'sale', 'waste')),
    quantity_change real not null check (quantity_change <> 0),
    movement_date timestamp not null,
    warehouse_item_id int not null,
    emp_id int not null,
    foreign key (warehouse_item_id) references Warehouse_Item (item_id),
    foreign key (emp_id) references Employee (emp_id)
);

create table Payment (
    payment_id int primary key auto_increment,
    payment_date timestamp not null,
    amount real not null,
    method varchar(32) check (method in ('cash', 'card')),
    payment_type varchar(32) check (payment_type in ('order', 'purchase')),  -- determines which fk is used
    order_id int,
    purchase_id int,
    foreign key (order_id) references Orders (order_id),
    foreign key (purchase_id) references Purchase (purchase_id)
);

-- insertion of dummy data in required tables for module
insert into Customer (customer_name, phone_number, email) values
('Ahmad Saleh', '0599123456', 'ahmad@gmail.com'),
('Lina Khaled', '0598234567', 'lina@gmail.com'),
('Omar Nasser', '0597345678', 'omar@gmail.com'),
('Sara Yasin', '0596456789', 'sara@gmail.com'),
('Yousef Hamdan', '0595567890', 'yousef@gmail.com');

insert into Employee (emp_name, salary, phone_number, position_title) values
('Ali Hassan', 2500, '0591111111', 'cashier'),
('Maya Taha', 2700, '0592222222', 'waiter'),
('Khaled Saad', 3000, '0593333333', 'manager');

insert into Menu_Item (item_name, category, price, date_added) values
('Espresso', 'drink', 8, '2024-01-01'),
('Cappuccino', 'drink', 10, '2024-01-01'),
('Latte', 'drink', 11, '2024-01-01'),
('Cheesecake', 'dessert', 15, '2024-01-05'),
('Brownie', 'dessert', 12, '2024-01-05'),
('Croissant', 'bakery', 7, '2024-01-10');

insert into Warehouse_Item (item_name, stock_quantity, reorder_level, unit_of_measure) values
('Coffee Beans', 10, 3, 'kg'),
('Milk', 20, 5, 'liter'),
('Sugar', 15, 5, 'kg'),
('Flour', 25, 8, 'kg'),
('Butter', 10, 3, 'kg'),
('Chocolate', 8, 2, 'kg'),
('Cheese', 6, 2, 'kg');
 
insert into Recipe values
(1, 1, 0.02), -- Espresso needs coffee beans
(2, 1, 0.02),
(2, 2, 0.15),
(3, 1, 0.02),
(3, 2, 0.20),
(4, 7, 0.10),
(4, 6, 0.05),
(5, 6, 0.07),
(6, 4, 0.10),
(6, 5, 0.05);

insert into Table_Entity (capacity) values
(2),
(2),
(4),
(4),
(4),
(4),
(7),
(7),
(2),
(2),
(2),
(2),
(2),
(2),
(6);


show tables;



