import sqlite3

try:
    conn = sqlite3.connect('drugs.db')
    c = conn.cursor()
    c.execute('SELECT name FROM sqlite_master WHERE type="table" AND name="drugs"')
    if c.fetchone():
        print("Table 'drugs' exists")
        c.execute('SELECT * FROM drugs')
        drugs = c.fetchall()
        if drugs:
            print("Data in drugs table:")
            for drug in drugs:
                print(f"ID: {drug[0]}")
                print(f"Name: {drug[1]}")
                print(f"Active Ingredient: {drug[2]}")
                print(f"Concentration: {drug[3]}")
                print(f"Form: {drug[4]}")
                print(f"Price: {drug[5]}")
                print(f"Manufacturer: {drug[6]}")
                print(f"Category: {drug[7]}")
                print(f"Uses: {drug[8]}")
                print(f"Contraindications: {drug[9]}")
                print(f"Precautions: {drug[10]}")
                print(f"Interactions: {drug[11]}")
                print(f"Storage Conditions: {drug[12]}")
                print(f"How to Use: {drug[13]}")
                print("-" * 50)
        else:
            print("Table 'drugs' is empty")
    else:
        print("Table 'drugs' does not exist")
except sqlite3.Error as e:
    print("Error accessing database:", e)
finally:
    conn.close()