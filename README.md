# Sales Intelligence Hub

## Project Overview

Sales Intelligence Hub is a web-based Sales Management and Analytics application developed using Python, Streamlit, MySQL, and Pandas.

The application provides centralized management of customer sales, payments, pending collections, branch performance, user access, and sales analytics.

## Technology Stack

- Python
- Streamlit
- MySQL
- Pandas
- MySQL Connector/Python
- ReportLab

## Project Structure

- `app.py` - Main Streamlit application
- `sales_management.sql` - MySQL database schema, sample data, and trigger implementation
- `requirements.txt` - Python dependencies
- `database_check.sql` - SQL queries for database verification

## Database

**Database Name:**

`sales_management`

**Database Configuration:**

- Host: `localhost`
- Port: `3306`
- User: `root`
- Database: `sales_management`

The database contains the following tables:

- `branches`
- `customer_sales`
- `payment_splits`
- `users`

The `customer_sales` table uses a generated column for calculating pending amounts.

A database trigger is implemented on the `payment_splits` table to automatically update the received amount and sale status when a payment is recorded.

## Key Features

### Authentication and Access Control

- User login and logout
- Session-based authentication
- Role-based access control
- Super Admin access
- Branch-level Admin access
- User management for Super Admin

### Sales Management

- Add new customer sales
- View customer sales
- Search sales records
- Filter sales by branch, product, status, and date
- Track gross sales
- Track received payments
- Track pending amounts
- Monitor Open and Close sales status

### Payment Management

- Record customer payments
- Support split payments
- Payment method tracking
- Payment validation against pending amount
- Automatic received amount calculation
- Automatic sale status update through database trigger

### Dashboard and Analytics

- Total sales
- Total received amount
- Pending collections
- Collection percentage
- Branch-wise sales analysis
- Product-wise analysis
- Payment method analysis
- Monthly sales trends
- Sales status analysis
- Branch contribution analysis

### Reports

- Filtered Sales Report
- CSV export
- Payment collection reports
- Pending collection reports
- PDF Sales Report

### SQL Analysis

The application provides predefined SQL analytical queries covering:

- Total sales
- Total collections
- Pending collections
- Branch-wise sales
- Average sales
- Payment analysis
- Monthly sales
- Top sales
- Sales status analysis

## Installation

### 1. Install Python

Install Python 3.11 or later.

### 2. Install Project Dependencies

Open PowerShell or Command Prompt inside the project folder and run:

```bash
python -m pip install -r requirements.txt
```

### 3. Configure MySQL

Create the `sales_management` database and execute:

`sales_management.sql`

The SQL file contains the required database tables, sample data, generated column, and trigger implementation.

### 4. Run the Application

Run the following command:

```bash
python -m streamlit run app.py
```

### 5. Open the Application

Open the following URL in a browser:

```text
http://localhost:8501
```

## Login

The application authenticates users using the `users` table.

**Default Super Admin:**

- Username: `admin`
- Password: `admin123`

For security, database credentials and default passwords should be changed before production deployment.

## Payment Automation

When a payment is inserted into `payment_splits`, the database trigger:

`trg_payment_after_insert`

calculates the total amount received for the corresponding sale and updates the sale status.

If the total received amount is equal to or greater than the gross sales amount, the sale is marked as:

`Close`

Otherwise, it remains:

`Open`

The pending amount is calculated using:

`Gross Sales - Received Amount`

## Role-Based Access

### Super Admin

Super Admin users can:

- View overall sales information
- Access analytics
- Manage users
- Create Admin users
- Access all branches

### Admin

Admin users can:

- View sales for their assigned branch
- Add sales
- Record payments
- View sales reports
- Access branch-level analytics

## Project Objective

The objective of the Sales Intelligence Hub is to provide a centralized platform for sales management, payment tracking, branch-level monitoring, and business analytics using a relational MySQL database and a Streamlit-based user interface.
