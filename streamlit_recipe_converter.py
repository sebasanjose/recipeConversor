import streamlit as st
import sqlite3
from pint import UnitRegistry
from pint.errors import UndefinedUnitError
import pandas as pd

# Initialize SQLite database
conn = sqlite3.connect('recipes.db', check_same_thread=False)
c = conn.cursor()

# Create tables if they don't exist
c.execute("""
CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER,
    name TEXT,
    quantity REAL,
    unit TEXT,
    FOREIGN KEY(recipe_id) REFERENCES recipes(id)
)
""")
conn.commit()

# Unit registry for conversions
ureg = UnitRegistry()
Q_ = ureg.Quantity

st.title("Recipe Converter")

# Sidebar navigation
menu = st.sidebar.selectbox("Menu", ["View/Edit Recipes", "Add Recipe", "Convert Recipe"])

# --- Add Recipe ---
if menu == "Add Recipe":
    st.header("Add New Recipe")
    recipe_name = st.text_input("Recipe Name")
    st.write("Enter ingredients (at least one row):")

    # Initialize row count
    if 'add_rows' not in st.session_state:
        st.session_state.add_rows = 1

    if st.button("Add Ingredient Row", key="add_row_btn"):
        st.session_state.add_rows += 1

    ingredients = []
    for i in range(st.session_state.add_rows):
        col1, col2, col3 = st.columns([3, 2, 2])
        with col1:
            name = st.text_input(f"Ingredient {i+1} Name", key=f"add_name_{i}")
        with col2:
            qty = st.number_input("Quantity", min_value=0.0, format="%f", key=f"add_qty_{i}")
        with col3:
            unit = st.text_input("Unit", key=f"add_unit_{i}")
        ingredients.append({"name": name, "quantity": qty, "unit": unit})

    if st.button("Save Recipe", key="save_add"):
        if not recipe_name:
            st.error("Please enter a recipe name.")
        else:
            c.execute("INSERT INTO recipes (name) VALUES (?)", (recipe_name,))
            rid = c.lastrowid
            count = 0
            for ing in ingredients:
                if ing["name"]:
                    c.execute(
                        "INSERT INTO ingredients (recipe_id, name, quantity, unit) VALUES (?, ?, ?, ?)",
                        (rid, ing["name"], ing["quantity"], ing["unit"])
                    )
                    count += 1
            conn.commit()
            st.success(f"Saved recipe '{recipe_name}' with {count} ingredients.")
            # reset
            st.session_state.add_rows = 1
            for key in list(st.session_state.keys()):
                if key.startswith("add_name_") or key.startswith("add_qty_") or key.startswith("add_unit_"):
                    del st.session_state[key]

# --- View & Edit Recipes ---
elif menu == "View Recipes":
    st.header("Recipes")
    recs = c.execute("SELECT id, name FROM recipes").fetchall()
    if not recs:
        st.info("No recipes added yet.")
    else:
        sel = st.selectbox("Select Recipe", [f"{r[0]}: {r[1]}" for r in recs])
        rid = int(sel.split(":")[0])

        # Load recipe details
        recipe = c.execute("SELECT name FROM recipes WHERE id = ?", (rid,)).fetchone()
        ingredients = c.execute(
            "SELECT name, quantity, unit FROM ingredients WHERE recipe_id = ?", (rid,)
        ).fetchall()
        df_ing = pd.DataFrame(ingredients, columns=["Ingredient", "Quantity", "Unit"])

        # Edit mode toggle
        edit_key = f"edit_mode_{rid}"
        if edit_key not in st.session_state:
            st.session_state[edit_key] = False

        if not st.session_state[edit_key]:
            # Display view
            st.subheader(recipe[0])
            st.table(df_ing)
            if st.button("Edit Recipe", key=f"edit_btn_{rid}"):
                st.session_state[edit_key] = True
                # prepare edit rows
                st.session_state[f"edit_rows_{rid}"] = len(ingredients) or 1
        else:
            # Edit form
            st.subheader(f"Edit '{recipe[0]}'")
            edit_name = st.text_input("Recipe Name", value=recipe[0], key=f"edit_name_{rid}")

            # row count for editing
            rows_key = f"edit_rows_{rid}"
            if st.button("Add Ingredient Row", key=f"edit_add_row_{rid}"):
                st.session_state[rows_key] += 1

            edit_ings = []
            for i in range(st.session_state[rows_key]):
                col1, col2, col3 = st.columns([3,2,2])
                with col1:
                    default = ingredients[i][0] if i < len(ingredients) else ""
                    name = st.text_input(f"Ingredient {i+1} Name", value=default, key=f"edit_name_{rid}_{i}")
                with col2:
                    default = ingredients[i][1] if i < len(ingredients) else 0.0
                    qty = st.number_input("Quantity", min_value=0.0, format="%f", value=default, key=f"edit_qty_{rid}_{i}")
                with col3:
                    default = ingredients[i][2] if i < len(ingredients) else ""
                    unit = st.text_input("Unit", value=default, key=f"edit_unit_{rid}_{i}")
                edit_ings.append({"name": name, "quantity": qty, "unit": unit})

            # Save or cancel
            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.button("Save Changes", key=f"save_edit_{rid}"):
                    # update recipe name
                    c.execute("UPDATE recipes SET name = ? WHERE id = ?", (edit_name, rid))
                    # delete old ingredients
                    c.execute("DELETE FROM ingredients WHERE recipe_id = ?", (rid,))
                    # insert new ingredients
                    for ing in edit_ings:
                        if ing["name"]:
                            c.execute(
                                "INSERT INTO ingredients (recipe_id, name, quantity, unit) VALUES (?, ?, ?, ?)",
                                (rid, ing["name"], ing["quantity"], ing["unit"])
                            )
                    conn.commit()
                    st.success("Recipe updated.")
                    # exit edit mode
                    st.session_state[edit_key] = False
            with col_cancel:
                if st.button("Cancel", key=f"cancel_edit_{rid}"):
                    st.session_state[edit_key] = False

# --- Convert Recipe ---
elif menu == "Convert Recipe":
    st.header("Convert Recipe")
    recs = c.execute("SELECT id, name FROM recipes").fetchall()
    if not recs:
        st.info("No recipes available. Please add one first.")
    else:
        sel = st.selectbox("Select Recipe to Convert", [f"{r[0]}: {r[1]}" for r in recs])
        rid = int(sel.split(":")[0])
        ingredients = c.execute(
            "SELECT name, quantity, unit FROM ingredients WHERE recipe_id = ?", (rid,)
        ).fetchall()
        df_ing = pd.DataFrame(ingredients, columns=["name", "quantity", "unit"])
        st.subheader("Original Ingredients")
        st.table(df_ing.rename(columns={"name": "Ingredient", "quantity": "Quantity", "unit": "Unit"}))

        key_ing = st.selectbox("Key Ingredient", df_ing["name"])
        default_unit = df_ing[df_ing["name"] == key_ing]["unit"].iloc[0]
        new_qty = st.number_input("New Quantity", value=1.0, min_value=0.0, format="%f")
        new_unit = st.text_input("New Unit", value=default_unit)

        if st.button("Convert", key="convert_btn"):
            orig_row = df_ing[df_ing["name"] == key_ing].iloc[0]
            try:
                orig = Q_(orig_row["quantity"], orig_row["unit"])
                target = Q_(new_qty, new_unit)
                factor = target.to(orig.units).magnitude / orig.magnitude
            except UndefinedUnitError:
                factor = new_qty / orig_row["quantity"] if orig_row["quantity"] else 0

            conv_list = []
            for _, row in df_ing.iterrows():
                try:
                    q = Q_(row["quantity"], row["unit"])
                    scaled = q * factor
                    qty_num = round(scaled.magnitude, 3)
                    unit_str = str(scaled.units)
                except UndefinedUnitError:
                    qty_num = round(row["quantity"] * factor, 3)
                    unit_str = row["unit"]
                conv_list.append({
                    "Ingredient": row["name"],
                    "Quantity": qty_num,
                    "Unit": unit_str
                })
            df_conv = pd.DataFrame(conv_list)
            st.subheader("Converted Ingredients")
            st.table(df_conv)

# Footer
st.sidebar.write("© Recipe Converter (local SaaS)")
