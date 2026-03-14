from flask import Flask, render_template, request, redirect
import sqlite3
from collections import deque

app = Flask(__name__)

order_queue = deque()
deleted_stack = []   # STACK for undo delete

# ---------------- DATABASE ----------------

def connect_db():
    conn = sqlite3.connect("inventory.db", timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = connect_db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        category TEXT,
        price REAL,
        quantity INTEGER
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS sales(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT,
        quantity INTEGER,
        price REAL
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- DASHBOARD ----------------

@app.route("/")
def dashboard():

    sort = request.args.get("sort")

    conn = connect_db()

    if sort == "low":
        products = conn.execute(
            "SELECT * FROM products ORDER BY price ASC"
        ).fetchall()

    elif sort == "high":
        products = conn.execute(
            "SELECT * FROM products ORDER BY price DESC"
        ).fetchall()

    elif sort == "category":
        products = conn.execute(
            "SELECT * FROM products ORDER BY category ASC"
        ).fetchall()

    else:
        products = conn.execute(
            "SELECT * FROM products"
        ).fetchall()

    inventory_value = sum(p["price"] * p["quantity"] for p in products)

    demand = conn.execute("""
        SELECT product_name, COUNT(*) as total
        FROM sales
        GROUP BY product_name
        ORDER BY total DESC
    """).fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        products=products,
        inventory_value=inventory_value,
        orders=len(order_queue),
        demand=demand
    )
# ---------------- ADD PRODUCT ----------------

@app.route("/add", methods=["GET","POST"])
def add_product():

    if request.method == "POST":

        name = request.form["name"]
        category = request.form["category"]
        price = float(request.form["price"])
        quantity = int(request.form["quantity"])

        conn = connect_db()

        product = conn.execute(
            "SELECT * FROM products WHERE name=?",
            (name,)
        ).fetchone()

        # AUTO RESTOCK
        if product:

            new_quantity = product["quantity"] + quantity

            conn.execute(
                "UPDATE products SET quantity=? WHERE name=?",
                (new_quantity,name)
            )

        else:

            conn.execute(
                "INSERT INTO products(name,category,price,quantity) VALUES(?,?,?,?)",
                (name,category,price,quantity)
            )

        conn.commit()
        conn.close()

        return redirect("/")

    return render_template("add_product.html")

# ---------------- DELETE PRODUCT ----------------

@app.route("/delete/<int:id>")
def delete_product(id):

    conn = connect_db()

    product = conn.execute(
        "SELECT * FROM products WHERE id=?",(id,)
    ).fetchone()

    if product:
        deleted_stack.append(dict(product))

    conn.execute("DELETE FROM products WHERE id=?",(id,))
    conn.commit()
    conn.close()

    return redirect("/")

# ---------------- UNDO DELETE ----------------

@app.route("/undo")
def undo_delete():

    if deleted_stack:

        product = deleted_stack.pop()

        conn = connect_db()

        conn.execute(
            "INSERT INTO products(name,category,price,quantity) VALUES(?,?,?,?)",
            (product["name"],product["category"],product["price"],product["quantity"])
        )

        conn.commit()
        conn.close()

    return redirect("/")

# ---------------- ORDER ----------------

@app.route("/order/<int:id>")
def order_product(id):

    order_queue.append(id)

    return redirect("/")

# ---------------- PROCESS ORDER ----------------

@app.route("/process")
def process_order():

    if not order_queue:
        return redirect("/")

    pid = order_queue.popleft()

    conn = connect_db()
    cursor = conn.cursor()

    product = cursor.execute(
        "SELECT * FROM products WHERE id=?",
        (pid,)
    ).fetchone()

    if product and product["quantity"] > 0:

        new_quantity = product["quantity"] - 1

        cursor.execute(
            "UPDATE products SET quantity=? WHERE id=?",
            (new_quantity, pid)
        )

        cursor.execute(
            "INSERT INTO sales(product_name,quantity,price) VALUES(?,?,?)",
            (product["name"], 1, product["price"])
        )

        conn.commit()

    conn.close()

    return redirect("/")

# ---------------- SALES PAGE ----------------

@app.route("/sales")
def sales():

    conn = connect_db()

    sales = conn.execute("SELECT * FROM sales").fetchall()

    conn.close()

    return render_template("sales.html",sales=sales)


# ---------------- RUN ----------------

if __name__ == "__main__":
    app.run(debug=True)