
import streamlit as st
import mysql.connector
import pandas as pd
from io import BytesIO
from datetime import date
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

st.set_page_config(page_title="Sales Intelligence Hub", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "REDACTED",
    "database": "sales_management",
}

PRODUCTS = ["DS", "DA", "BA", "FSD", "BI", "AI", "ML", "SQL"]
PAYMENT_METHODS = ["Cash", "UPI", "Card"]

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)

def money(x):
    return f"₹{float(x or 0):,.0f}"

def query_df(sql, params=None):
    conn = get_connection()
    try:
        return pd.read_sql(sql, conn, params=params)
    finally:
        conn.close()

def execute(sql, params=None):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql, params or ())
        conn.commit()
        return cur.lastrowid
    finally:
        cur.close()
        conn.close()

def authenticate(username, password):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT user_id, username, password, branch_id, role, email
               FROM users WHERE username=%s AND password=%s LIMIT 1""",
            (username.strip(), password),
        )
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()

def load_branches():
    return query_df(
        "SELECT branch_id, branch_name, branch_admin_name FROM branches ORDER BY branch_name"
    )

def load_sales():
    return query_df(
        """SELECT cs.sale_id, cs.branch_id, b.branch_name, cs.date,
                  cs.name, cs.mobile_number, cs.product_name,
                  cs.gross_sales, cs.received_amount, cs.pending_amount, cs.status
           FROM customer_sales cs
           LEFT JOIN branches b ON cs.branch_id=b.branch_id
           ORDER BY cs.date, cs.sale_id"""
    )

def login_page():
    st.markdown(
        """<style>
        [data-testid="stMainBlockContainer"] {
            max-width: 520px !important;
            margin-left: auto !important;
            margin-right: auto !important;
            padding-top: 90px !important;
        }
        .login-title {
            text-align: center;
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 4px;
        }
        .login-subtitle {
            text-align: center;
            color: #a8acb8;
            margin-bottom: 30px;
            font-size: 16px;
        }
        [data-testid="stTextInput"] { width: 100%; }
        [data-testid="stTextInput"] input { width: 100%; }
        [data-testid="stButton"] button { width: 100%; }
        </style>""",
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="login-title">📊 Sales Intelligence Hub</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="login-subtitle">Login to access the sales management system</div>',
        unsafe_allow_html=True,
    )

    u = st.text_input("Username", placeholder="Enter username")
    p = st.text_input("Password", type="password", placeholder="Enter password")

    if st.button("🔐 Login", type="primary", use_container_width=True):
        if not u or not p:
            st.error("Please enter username and password.")
        else:
            try:
                user = authenticate(u, p)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
            except Exception as e:
                st.error(f"Database connection error: {e}")


if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.logged_in:
    login_page()
    st.stop()

USER = st.session_state.user

# Ensure the required AFTER INSERT payment trigger exists.
# It updates received_amount; pending_amount is a generated column in the project schema.
def ensure_payment_trigger():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT COUNT(*) FROM information_schema.TRIGGERS
               WHERE TRIGGER_SCHEMA=%s AND TRIGGER_NAME=%s""",
            (DB_CONFIG["database"], "trg_payment_after_insert"),
        )
        exists = cur.fetchone()[0] > 0
        if not exists:
            cur.execute(
                """CREATE TRIGGER trg_payment_after_insert
                   AFTER INSERT ON payment_splits
                   FOR EACH ROW
                   UPDATE customer_sales
                   SET received_amount = (
                       SELECT COALESCE(SUM(amount_paid),0)
                       FROM payment_splits
                       WHERE sale_id = NEW.sale_id
                   ),
                   status = CASE
                       WHEN (
                           SELECT COALESCE(SUM(amount_paid),0)
                           FROM payment_splits
                           WHERE sale_id = NEW.sale_id
                       ) >= gross_sales THEN 'Close'
                       ELSE 'Open'
                   END
                   WHERE sale_id = NEW.sale_id"""
            )
            conn.commit()
    finally:
        cur.close()
        conn.close()

try:
    ensure_payment_trigger()
except Exception as e:
    # Do not stop the whole application if the DB account cannot create a trigger.
    st.session_state["trigger_warning"] = str(e)

branches = load_branches()

with st.sidebar:
    st.markdown("## 👤 Logged In")
    st.write(f"**Username:** {USER['username']}")
    st.write(f"**Role:** {USER['role']}")
    st.write(f"**Email:** {USER['email']}")
    if USER.get("branch_id") is not None:
        st.write(f"**Branch ID:** {USER['branch_id']}")
    st.divider()

    menu = ["Dashboard", "Add Sale", "Add Payment", "Sales Report", "Analytics", "SQL Analysis"]
    if USER["role"] == "Super Admin":
        menu.append("User Access")

    page = st.radio("Navigation", menu)

    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.rerun()

if "trigger_warning" in st.session_state:
    st.sidebar.warning(
        "Payment trigger could not be verified/created. "
        "Add Payment may require the MySQL user to have TRIGGER privilege."
    )

# ---------------- DASHBOARD ----------------
def dashboard():
    df = load_sales()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    if USER["role"] == "Admin" and USER.get("branch_id") is not None:
        df = df[df.branch_id == USER["branch_id"]].copy()

    st.title("📊 Sales Intelligence Hub")
    st.caption("Sales dashboard connected to MySQL")

    st.subheader("🔎 Dashboard Filters")
    branch_options = ["All"] + sorted(df.branch_name.dropna().astype(str).unique().tolist())
    product_options = ["All"] + sorted(df.product_name.dropna().astype(str).unique().tolist())
    status_options = ["All"] + sorted(df.status.dropna().astype(str).unique().tolist())

    mn = df.date.min().date() if not df.empty else date.today()
    mx = df.date.max().date() if not df.empty else date.today()

    def reset_filters():
        st.session_state["branch_filter"] = "All"
        st.session_state["product_filter"] = "All"
        st.session_state["status_filter"] = "All"
        st.session_state["date_filter"] = (mn, mx)

    st.button("🔄 Reset Filters", on_click=reset_filters)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        branch = st.selectbox("Branch", branch_options, key="branch_filter")
    with c2:
        product = st.selectbox("Product", product_options, key="product_filter")
    with c3:
        status = st.selectbox("Status", status_options, key="status_filter")
    with c4:
        dates = st.date_input(
            "Date Range",
            value=(mn, mx),
            min_value=mn,
            max_value=mx,
            key="date_filter",
        )

    if isinstance(dates, (tuple, list)):
        if len(dates) >= 2:
            start, end = dates[0], dates[-1]
        elif len(dates) == 1:
            start = end = dates[0]
        else:
            start = end = mn
    else:
        start = end = dates

    start = pd.to_datetime(start).date()
    end = pd.to_datetime(end).date()

    f = df.copy()
    if branch != "All":
        f = f[f.branch_name == branch]
    if product != "All":
        f = f[f.product_name == product]
    if status != "All":
        f = f[f.status == status]
    f = f[(f.date.dt.date >= start) & (f.date.dt.date <= end)].copy()

    st.info(f"📌 Showing {len(f):,} sales records")

    total = f.gross_sales.sum()
    received = f.received_amount.sum()
    pending_total = f.pending_amount.sum()
    collection = received / total * 100 if total else 0

    st.header("📊 Sales Overview")
    a, b, c, d = st.columns(4)
    a.metric("💰 Total Sales", money(total))
    b.metric("💵 Total Received", money(received))
    c.metric("⏳ Total Pending", money(pending_total))
    d.metric("📈 Collection %", f"{collection:.2f}%")

    st.header("Customer Sales Data")

    # Search across the displayed sales data
    search_text = st.text_input(
        "🔍 Search Sales",
        placeholder="Search by Sale ID, customer, mobile, product, branch, status...",
    )

    cols = [
        "sale_id", "branch_id", "branch_name", "date", "name",
        "mobile_number", "product_name", "gross_sales",
        "received_amount", "pending_amount", "status"
    ]
    sales = f[cols].copy()

    if search_text.strip():
        search_value = search_text.strip().lower()
        searchable = sales.astype(str).apply(
            lambda column: column.str.lower().str.contains(
                search_value, regex=False, na=False
            )
        )
        sales = sales[searchable.any(axis=1)].copy()

    st.info(f"🔎 Showing {len(sales):,} matching sales records")
    sales["date"] = sales.date.dt.strftime("%Y-%m-%d")
    st.dataframe(sales, use_container_width=True)
    st.download_button(
        "📥 Download Filtered Sales CSV",
        sales.to_csv(index=False).encode(),
        "filtered_sales.csv",
        "text/csv",
    )

    st.header("🏢 Branch-wise Sales")
    branch_sales = (
        f.groupby("branch_name", as_index=False).gross_sales.sum()
        .rename(columns={"gross_sales": "total_sales"})
        .sort_values("total_sales", ascending=False)
    )
    if not branch_sales.empty:
        st.bar_chart(branch_sales.set_index("branch_name").total_sales)

    st.header("📦 Sales by Product")
    product_sales = (
        f.groupby("product_name", as_index=False).gross_sales.sum()
        .rename(columns={"gross_sales": "total_sales"})
        .sort_values("total_sales", ascending=False)
    )
    if not product_sales.empty:
        st.bar_chart(product_sales.set_index("product_name").total_sales)

    st.header("📈 Monthly Sales Trend")
    ms = f.copy()
    ms["month"] = ms.date.dt.to_period("M").astype(str)
    ms = (
        ms.groupby("month", as_index=False).gross_sales.sum()
        .rename(columns={"gross_sales": "total_sales"})
        .sort_values("month")
    )
    best = lowest = None
    if not ms.empty:
        st.line_chart(ms.set_index("month").total_sales)
        best = ms.loc[ms.total_sales.idxmax()]
        lowest = ms.loc[ms.total_sales.idxmin()]
        x, y = st.columns(2)
        x.metric(f"🏆 Best Sales Month ({best['month']})", money(best["total_sales"]))
        y.metric(f"📉 Lowest Sales Month ({lowest['month']})", money(lowest["total_sales"]))

    st.header("📊 Branch Sales Contribution")
    contribution = branch_sales.copy()
    contribution["sales_percentage"] = contribution.total_sales / total * 100 if total else 0
    st.dataframe(contribution, use_container_width=True)
    st.download_button(
        "📥 Download Branch Contribution CSV",
        contribution.to_csv(index=False).encode(),
        "branch_contribution.csv",
        "text/csv",
    )

    st.header("💳 Collection by Payment Method")
    payment = pd.DataFrame()
    try:
        q = """SELECT ps.payment_method,
                       SUM(ps.amount_paid) AS total_collection
                FROM payment_splits ps
                INNER JOIN customer_sales cs ON ps.sale_id=cs.sale_id
                WHERE cs.date BETWEEN %s AND %s"""
        params = [start, end]

        if USER["role"] == "Admin" and USER.get("branch_id") is not None:
            q += " AND cs.branch_id=%s"
            params.append(int(USER["branch_id"]))
        elif branch != "All":
            bid = f.branch_id.iloc[0] if not f.empty else None
            if bid is None:
                q += " AND 1=0"
            else:
                q += " AND cs.branch_id=%s"
                params.append(int(bid))

        if product != "All":
            q += " AND cs.product_name=%s"
            params.append(product)
        if status != "All":
            q += " AND cs.status=%s"
            params.append(status)

        q += " GROUP BY ps.payment_method ORDER BY total_collection DESC"
        payment = query_df(q, params)
    except Exception as e:
        st.warning(f"Payment collection data unavailable: {e}")

    if not payment.empty:
        st.bar_chart(payment.set_index("payment_method").total_collection)
        st.dataframe(payment, use_container_width=True)
        st.download_button(
            "📥 Download Payment Collection CSV",
            payment.to_csv(index=False).encode(),
            "payment_collection.csv",
            "text/csv",
        )
    else:
        st.info("No payment collection data for the selected filters.")

    st.header("⏳ Pending Collections")
    ps = f[f.pending_amount > 0].sort_values("pending_amount", ascending=False)
    pending_display = ps[
        ["sale_id", "name", "gross_sales", "received_amount", "pending_amount", "status"]
    ].head(100)
    st.dataframe(pending_display, use_container_width=True)
    st.download_button(
        "📥 Download Pending Collections CSV",
        pending_display.to_csv(index=False).encode(),
        "pending_collections.csv",
        "text/csv",
    )

    st.header("📌 Highest Pending Customer")
    if not ps.empty:
        top = ps.iloc[0]
        h1, h2, h3 = st.columns(3)
        h1.metric("Customer", top["name"])
        h2.metric("Gross Sales", money(top["gross_sales"]))
        h3.metric("Pending Amount", money(top["pending_amount"]))

    st.header("📌 Sales Status Analysis")
    status_analysis = f.groupby("status", as_index=False).agg(
        number_of_sales=("sale_id", "count"),
        total_sales=("gross_sales", "sum"),
        total_received=("received_amount", "sum"),
        total_pending=("pending_amount", "sum"),
    )
    st.dataframe(status_analysis, use_container_width=True)
    if not status_analysis.empty:
        st.bar_chart(
            status_analysis.set_index("status")[
                ["total_sales", "total_received", "total_pending"]
            ]
        )

    st.header("💰 Collection Efficiency")
    e1, e2 = st.columns(2)
    e1.metric("Collection Percentage", f"{collection:.2f}%")
    e2.metric("Pending Percentage", f"{100 - collection:.2f}%")

    # PDF
    def make_pdf():
        b = BytesIO()
        doc = SimpleDocTemplate(
            b, pagesize=landscape(A4),
            rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24
        )
        styles = getSampleStyleSheet()
        title = ParagraphStyle(
            "title", parent=styles["Title"], alignment=TA_CENTER, fontSize=20
        )
        story = [
            Paragraph("Sales Intelligence Hub", title),
            Paragraph(f"Generated for: {USER['username']} ({USER['role']})", styles["Normal"]),
            Spacer(1, 10),
        ]
        summary = Table(
            [["Total Sales", "Total Received", "Total Pending", "Collection %"],
             [money(total), money(received), money(pending_total), f"{collection:.2f}%"]],
            colWidths=[180] * 4,
        )
        summary.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1f2937")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("GRID", (0,0), (-1,-1), .5, colors.grey),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("TOPPADDING", (0,0), (-1,-1), 7),
            ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ]))
        story += [summary, Spacer(1, 12)]

        if best is not None:
            story.append(Paragraph(
                f"Best Sales Month: {best['month']} - {money(best['total_sales'])}",
                styles["Normal"]
            ))
        if lowest is not None:
            story.append(Paragraph(
                f"Lowest Sales Month: {lowest['month']} - {money(lowest['total_sales'])}",
                styles["Normal"]
            ))

        def add_df(df2, title_text, n=30):
            out = [Paragraph(title_text, styles["Heading2"])]
            if df2 is None or df2.empty:
                out.append(Paragraph("No data available.", styles["Normal"]))
                return out
            v = df2.head(n).fillna("")
            data = [list(v.columns)] + [
                [str(x) for x in row] for row in v.itertuples(index=False, name=None)
            ]
            w = 720 / max(1, len(data[0]))
            t = Table(data, repeatRows=1, colWidths=[w] * len(data[0]))
            t.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,-1), 6.5),
                ("GRID", (0,0), (-1,-1), .25, colors.grey),
            ]))
            out += [t, Spacer(1, 12)]
            return out

        story += [
            *add_df(contribution, "Branch Sales Contribution", 20),
            *add_df(payment, "Collection by Payment Method", 20),
            PageBreak(),
            *add_df(pending_display, "Pending Collections", 30),
            *add_df(status_analysis, "Sales Status Analysis", 20),
            *add_df(sales, "Filtered Sales Data", 50),
        ]
        doc.build(story)
        b.seek(0)
        return b.getvalue()

    st.header("📄 Reports")
    st.download_button(
        "📄 Download PDF Sales Report",
        make_pdf(),
        "sales_intelligence_report.pdf",
        "application/pdf",
    )

# ---------------- ADD SALE ----------------
def add_sale():
    st.title("➕ Add New Sale")
    st.caption("Create a new customer sales entry. Financial fields are calculated by the database logic.")

    branch_map = dict(zip(branches.branch_name, branches.branch_id))
    if USER["role"] == "Admin":
        allowed = branches[branches.branch_id == USER["branch_id"]]
    else:
        allowed = branches

    if allowed.empty:
        st.error("No branch is assigned/available for this user.")
        return

    selected_branch = st.selectbox("Branch", allowed.branch_name.tolist())
    sale_date = st.date_input("Sale Date", value=date.today())
    name = st.text_input("Customer Name")
    mobile = st.text_input("Mobile Number")
    product = st.selectbox("Product", PRODUCTS)
    gross_sales = st.number_input("Gross Sales Amount", min_value=0.0, step=100.0)

    st.info("Received Amount and Pending Amount are controlled by payment tracking/database triggers.")

    if st.button("💾 Save Sale", type="primary"):
        if not name.strip():
            st.error("Customer name is required.")
            return
        if not mobile.strip():
            st.error("Mobile number is required.")
            return
        if gross_sales <= 0:
            st.error("Gross sales must be greater than 0.")
            return

        try:
            sale_id = execute(
                """INSERT INTO customer_sales
                   (branch_id, date, name, mobile_number, product_name, gross_sales, status)
                   VALUES (%s,%s,%s,%s,%s,%s,'Open')""",
                (
                    int(branch_map[selected_branch]),
                    sale_date,
                    name.strip(),
                    mobile.strip(),
                    product,
                    float(gross_sales),
                ),
            )
            st.success(f"Sale created successfully. Sale ID: {sale_id}")
            st.info("Received amount starts from the payment records. Use Add Payment to record the collection.")
        except Exception as e:
            st.error(f"Unable to create sale: {e}")

# ---------------- ADD PAYMENT ----------------
def add_payment():
    st.title("💳 Add Payment / Split Payment")
    st.caption("Multiple payment records can be added against one sale.")

    sales = load_sales()
    if USER["role"] == "Admin":
        sales = sales[sales.branch_id == USER["branch_id"]].copy()

    if sales.empty:
        st.info("No sales are available for payment entry.")
        return

    open_sales = sales[sales.pending_amount > 0].copy()
    if open_sales.empty:
        st.success("There are no sales with pending amounts.")
        return

    open_sales["label"] = open_sales.apply(
        lambda r: f"Sale {int(r.sale_id)} | {r['name']} | {r.product_name} | Pending {money(r.pending_amount)}",
        axis=1,
    )
    label = st.selectbox("Select Sale", open_sales.label.tolist())
    selected_id = int(open_sales.loc[open_sales.label == label, "sale_id"].iloc[0])
    selected = open_sales[open_sales.sale_id == selected_id].iloc[0]

    c1, c2, c3 = st.columns(3)
    c1.metric("Gross Sales", money(selected.gross_sales))
    c2.metric("Received", money(selected.received_amount))
    c3.metric("Pending", money(selected.pending_amount))

    payment_date = st.date_input("Payment Date", value=date.today())
    amount = st.number_input(
        "Amount Paid",
        min_value=0.01,
        max_value=float(selected.pending_amount),
        step=100.0,
    )
    method = st.selectbox("Payment Method", PAYMENT_METHODS)

    if st.button("💾 Save Payment", type="primary"):
        if amount <= 0:
            st.error("Payment amount must be greater than 0.")
            return
        if amount > float(selected.pending_amount):
            st.error("Payment cannot be greater than the pending amount.")
            return

        try:
            payment_id = execute(
                """INSERT INTO payment_splits
                   (sale_id, payment_date, amount_paid, payment_method)
                   VALUES (%s,%s,%s,%s)""",
                (selected_id, payment_date, float(amount), method),
            )

            updated = load_sales()
            updated_row = updated[updated.sale_id == selected_id].iloc[0]
            st.success(f"Payment saved successfully. Payment ID: {payment_id}")
            st.write(
                f"Updated Received: **{money(updated_row.received_amount)}** | "
                f"Updated Pending: **{money(updated_row.pending_amount)}** | "
                f"Status: **{updated_row.status}**"
            )
            st.rerun()
        except Exception as e:
            st.error(f"Unable to save payment: {e}")

# ---------------- SALES REPORT ----------------
def sales_report():
    st.title("📋 Sales Report")
    st.caption("Filter and export sales records.")

    df = load_sales()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    if USER["role"] == "Admin":
        df = df[df.branch_id == USER["branch_id"]].copy()

    c1, c2, c3 = st.columns(3)
    with c1:
        branch_names = ["All"] + sorted(df.branch_name.dropna().unique().tolist())
        branch = st.selectbox("Branch", branch_names, key="report_branch")
    with c2:
        statuses = ["All"] + sorted(df.status.dropna().unique().tolist())
        status = st.selectbox("Status", statuses, key="report_status")
    with c3:
        products = ["All"] + sorted(df.product_name.dropna().unique().tolist())
        product = st.selectbox("Product", products, key="report_product")

    if branch != "All":
        df = df[df.branch_name == branch]
    if status != "All":
        df = df[df.status == status]
    if product != "All":
        df = df[df.product_name == product]

    if df.empty:
        st.warning("No records match the selected filters.")
        return

    st.metric("Records", len(df))
    st.metric("Gross Sales", money(df.gross_sales.sum()))
    st.metric("Pending", money(df.pending_amount.sum()))
    st.dataframe(df, use_container_width=True)
    st.download_button(
        "📥 Download Sales Report CSV",
        df.to_csv(index=False).encode(),
        "sales_report.csv",
        "text/csv",
    )

# ---------------- ANALYTICS ----------------
def analytics():
    st.title("📊 Analytics")
    df = load_sales()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    if USER["role"] == "Admin":
        df = df[df.branch_id == USER["branch_id"]].copy()

    total = df.gross_sales.sum()
    received = df.received_amount.sum()
    pending = df.pending_amount.sum()

    a, b, c, d = st.columns(4)
    a.metric("Total Revenue", money(total))
    b.metric("Received", money(received))
    c.metric("Pending", money(pending))
    d.metric("Collection %", f"{received / total * 100:.2f}%" if total else "0.00%")

    st.subheader("Branch Performance")
    branch_perf = df.groupby("branch_name", as_index=False).agg(
        total_sales=("gross_sales", "sum"),
        received=("received_amount", "sum"),
        pending=("pending_amount", "sum"),
        number_of_sales=("sale_id", "count"),
    ).sort_values("total_sales", ascending=False)
    st.dataframe(branch_perf, use_container_width=True)

    st.subheader("Monthly Growth")
    monthly = df.assign(month=df.date.dt.to_period("M").astype(str)).groupby(
        "month", as_index=False
    ).gross_sales.sum().rename(columns={"gross_sales": "total_sales"})
    st.line_chart(monthly.set_index("month"))

    st.subheader("Payment Method Analysis")
    payment = query_df(
        """SELECT ps.payment_method, SUM(ps.amount_paid) AS total_collection
           FROM payment_splits ps
           INNER JOIN customer_sales cs ON ps.sale_id=cs.sale_id
           GROUP BY ps.payment_method
           ORDER BY total_collection DESC"""
    )
    st.dataframe(payment, use_container_width=True)
    if not payment.empty:
        st.bar_chart(payment.set_index("payment_method").total_collection)

# ---------------- SQL ANALYSIS ----------------
SQL_QUERIES = {
    "1. All customer sales": "SELECT * FROM customer_sales;",
    "2. All branches": "SELECT * FROM branches;",
    "3. All payment splits": "SELECT * FROM payment_splits;",
    "4. Open sales": "SELECT * FROM customer_sales WHERE status='Open';",
    "5. Chennai branch sales": """SELECT cs.* FROM customer_sales cs
                                  INNER JOIN branches b ON cs.branch_id=b.branch_id
                                  WHERE b.branch_name='Chennai';""",
    "6. Total gross sales": "SELECT SUM(gross_sales) AS total_gross_sales FROM customer_sales;",
    "7. Total received": "SELECT SUM(received_amount) AS total_received FROM customer_sales;",
    "8. Total pending": "SELECT SUM(pending_amount) AS total_pending FROM customer_sales;",
    "9. Sales count per branch": """SELECT b.branch_name, COUNT(cs.sale_id) AS number_of_sales
                                    FROM branches b LEFT JOIN customer_sales cs
                                    ON b.branch_id=cs.branch_id
                                    GROUP BY b.branch_id,b.branch_name;""",
    "10. Average gross sales": "SELECT AVG(gross_sales) AS average_gross_sales FROM customer_sales;",
    "11. Sales with branch name": """SELECT cs.*, b.branch_name
                                     FROM customer_sales cs
                                     INNER JOIN branches b ON cs.branch_id=b.branch_id;""",
    "12. Sales with total payment received": """SELECT cs.sale_id, cs.name, cs.gross_sales,
                                                COALESCE(SUM(ps.amount_paid),0) AS total_payment_received
                                                FROM customer_sales cs
                                                LEFT JOIN payment_splits ps ON cs.sale_id=ps.sale_id
                                                GROUP BY cs.sale_id,cs.name,cs.gross_sales;""",
    "13. Branch-wise gross sales": """SELECT b.branch_name, SUM(cs.gross_sales) AS total_gross_sales
                                      FROM customer_sales cs
                                      INNER JOIN branches b ON cs.branch_id=b.branch_id
                                      GROUP BY b.branch_id,b.branch_name
                                      ORDER BY total_gross_sales DESC;""",
    "14. Sales with payment method": """SELECT cs.sale_id, cs.name, cs.gross_sales,
                                        ps.payment_method, ps.amount_paid
                                        FROM customer_sales cs
                                        INNER JOIN payment_splits ps ON cs.sale_id=ps.sale_id;""",
    "15. Sales with branch admin": """SELECT cs.sale_id, cs.name, b.branch_name,
                                      b.branch_admin_name
                                      FROM customer_sales cs
                                      INNER JOIN branches b ON cs.branch_id=b.branch_id;""",
    "16. Pending greater than 5000": "SELECT * FROM customer_sales WHERE pending_amount > 5000;",
    "17. Top 3 highest gross sales": "SELECT * FROM customer_sales ORDER BY gross_sales DESC LIMIT 3;",
    "18. Highest sales branch": """SELECT b.branch_name, SUM(cs.gross_sales) AS total_gross_sales
                                   FROM customer_sales cs
                                   INNER JOIN branches b ON cs.branch_id=b.branch_id
                                   GROUP BY b.branch_id,b.branch_name
                                   ORDER BY total_gross_sales DESC LIMIT 1;""",
    "19. Monthly sales summary": """SELECT YEAR(date) AS year, MONTH(date) AS month,
                                    SUM(gross_sales) AS total_sales
                                    FROM customer_sales
                                    GROUP BY YEAR(date), MONTH(date)
                                    ORDER BY year,month;""",
    "20. Payment method collection": """SELECT payment_method, SUM(amount_paid) AS total_collection
                                        FROM payment_splits
                                        GROUP BY payment_method
                                        ORDER BY total_collection DESC;""",
}

def sql_analysis():
    st.title("🧮 SQL Analysis")
    st.caption("Predefined analytical SQL queries from the project document.")

    name = st.selectbox("Select SQL Query", list(SQL_QUERIES.keys()))
    sql = SQL_QUERIES[name]
    st.code(sql, language="sql")

    if st.button("▶️ Execute Query", type="primary"):
        try:
            result = query_df(sql)
            st.success(f"Query executed successfully. {len(result):,} rows returned.")
            st.dataframe(result, use_container_width=True)
        except Exception as e:
            st.error(f"SQL execution error: {e}")

# ---------------- USER ACCESS ----------------
def user_access():
    st.title("👥 User Access")
    if USER["role"] != "Super Admin":
        st.error("Only Super Admin can access this section.")
        return

    st.subheader("Existing Users")
    users = query_df(
        """SELECT user_id, username, branch_id, role, email
           FROM users ORDER BY user_id"""
    )
    st.dataframe(users, use_container_width=True)

    st.subheader("Create Admin User")
    branch_map = dict(zip(branches.branch_name, branches.branch_id))
    c1, c2 = st.columns(2)
    with c1:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        email = st.text_input("Email")
    with c2:
        branch_name = st.selectbox("Assigned Branch", branches.branch_name.tolist())
        role = st.selectbox("Role", ["Admin", "Super Admin"])

    if st.button("➕ Create User"):
        if not username.strip() or not password or not email.strip():
            st.error("Username, password and email are required.")
            return
        try:
            new_id = execute(
                """INSERT INTO users (username,password,branch_id,role,email)
                   VALUES (%s,%s,%s,%s,%s)""",
                (
                    username.strip(), password,
                    int(branch_map[branch_name]) if role == "Admin" else None,
                    role, email.strip()
                ),
            )
            st.success(f"User created successfully. User ID: {new_id}")
            st.rerun()
        except Exception as e:
            st.error(f"Unable to create user: {e}")

if page == "Dashboard":
    dashboard()
elif page == "Add Sale":
    add_sale()
elif page == "Add Payment":
    add_payment()
elif page == "Sales Report":
    sales_report()
elif page == "Analytics":
    analytics()
elif page == "SQL Analysis":
    sql_analysis()
elif page == "User Access":
    user_access()
