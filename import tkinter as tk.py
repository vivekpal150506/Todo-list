import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import random
import math
from datetime import datetime, timedelta

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from sklearn.ensemble import RandomForestRegressor


# ============================================================
# SMART ENERGY MANAGEMENT SYSTEM - B.TECH PROJECT
# ============================================================

DB_NAME = "energy_management.db"

# Electricity tariff - ₹/kWh
TARIFF = 7.0

# Baseline used to calculate estimated energy saving
BASELINE_FACTOR = 1.20


# ============================================================
# DATABASE
# ============================================================

def create_database():

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS energy_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            power_kw REAL,
            voltage REAL,
            current_amp REAL,
            power_factor REAL,
            frequency REAL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appliance_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            appliance TEXT,
            power_kw REAL,
            energy_kwh REAL
        )
    """)

    conn.commit()
    conn.close()


# ============================================================
# GENERATE SIMULATED SMART METER DATA
# ============================================================

def generate_energy_data():

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Generate 7 days of hourly data
    start_time = datetime.now() - timedelta(days=7)

    cursor.execute("DELETE FROM energy_data")
    cursor.execute("DELETE FROM appliance_data")

    appliances = {
        "AC": 1.5,
        "Fan": 0.075,
        "Lights": 0.06,
        "Refrigerator": 0.18,
        "TV": 0.12,
        "Computer": 0.25,
        "Washing Machine": 0.5
    }

    for hour in range(24 * 7):

        timestamp = start_time + timedelta(hours=hour)

        h = timestamp.hour

        # Simulated daily load pattern
        base_load = (
            1.2
            + 0.5 * math.sin((h - 6) * math.pi / 12)
        )

        # Higher usage in evening
        if 18 <= h <= 22:
            base_load += 1.2

        if 10 <= h <= 16:
            base_load += 0.6

        power_kw = max(
            0.5,
            base_load + random.uniform(-0.25, 0.35)
        )

        voltage = random.uniform(225, 240)

        current = (
            power_kw * 1000
        ) / (voltage * 0.95)

        power_factor = random.uniform(0.88, 0.98)

        frequency = random.uniform(49.8, 50.2)

        cursor.execute("""
            INSERT INTO energy_data
            (timestamp, power_kw, voltage,
             current_amp, power_factor, frequency)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            power_kw,
            voltage,
            current,
            power_factor,
            frequency
        ))

        # Appliance consumption
        for appliance, rated_power in appliances.items():

            usage_probability = 0.2

            if appliance == "AC":
                usage_probability = 0.7 if 12 <= h <= 23 else 0.2

            elif appliance == "Fan":
                usage_probability = 0.8

            elif appliance == "Lights":
                usage_probability = 0.8 if h >= 18 or h <= 6 else 0.1

            elif appliance == "TV":
                usage_probability = 0.7 if 18 <= h <= 23 else 0.1

            elif appliance == "Computer":
                usage_probability = 0.6 if 9 <= h <= 18 else 0.1

            elif appliance == "Washing Machine":
                usage_probability = 0.3

            elif appliance == "Refrigerator":
                usage_probability = 0.9

            if random.random() < usage_probability:

                actual_power = rated_power

                energy = actual_power * 1

                cursor.execute("""
                    INSERT INTO appliance_data
                    (timestamp, appliance, power_kw, energy_kwh)
                    VALUES (?, ?, ?, ?)
                """, (
                    timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    appliance,
                    actual_power,
                    energy
                ))

    conn.commit()
    conn.close()


# ============================================================
# DATA FUNCTIONS
# ============================================================

def get_energy_dataframe():

    conn = sqlite3.connect(DB_NAME)

    df = pd.read_sql_query(
        "SELECT * FROM energy_data ORDER BY timestamp",
        conn
    )

    conn.close()

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    return df


def get_today_data():

    df = get_energy_dataframe()

    today = datetime.now().date()

    return df[df["timestamp"].dt.date == today]


def get_latest_data():

    conn = sqlite3.connect(DB_NAME)

    df = pd.read_sql_query("""
        SELECT *
        FROM energy_data
        ORDER BY timestamp DESC
        LIMIT 1
    """, conn)

    conn.close()

    return df


# ============================================================
# CALCULATIONS
# ============================================================

def daily_energy():

    df = get_today_data()

    if df.empty:
        return 0

    # Hourly data, therefore each sample represents approximately 1 hour
    return df["power_kw"].sum()


def monthly_energy():

    df = get_energy_dataframe()

    current_month = datetime.now().month

    df = df[
        df["timestamp"].dt.month == current_month
    ]

    if df.empty:
        return 0

    return df["power_kw"].sum()


def peak_power():

    df = get_today_data()

    if df.empty:
        return 0

    return df["power_kw"].max()


def estimated_bill():

    energy = monthly_energy()

    return energy * TARIFF


def energy_saving_percentage():

    energy = monthly_energy()

    if energy == 0:
        return 0

    baseline = energy * BASELINE_FACTOR

    saved = baseline - energy

    percentage = (saved / baseline) * 100

    return max(0, percentage)


# ============================================================
# NEXT-HOUR ML PREDICTION
# ============================================================

def next_hour_prediction():

    df = get_energy_dataframe()

    if len(df) < 10:
        return 0

    df["hour"] = df["timestamp"].dt.hour
    df["day"] = df["timestamp"].dt.day
    df["weekday"] = df["timestamp"].dt.weekday

    features = [
        "hour",
        "day",
        "weekday"
    ]

    X = df[features]
    y = df["power_kw"]

    model = RandomForestRegressor(
        n_estimators=100,
        random_state=42
    )

    model.fit(X, y)

    now = datetime.now()

    next_hour = now + timedelta(hours=1)

    future_data = pd.DataFrame({
        "hour": [next_hour.hour],
        "day": [next_hour.day],
        "weekday": [next_hour.weekday()]
    })

    prediction = model.predict(future_data)[0]

    return prediction


# ============================================================
# DASHBOARD
# ============================================================

class EnergyDashboard:

    def __init__(self, root):

        self.root = root

        self.root.title(
            "Smart Energy Management System"
        )

        self.root.geometry("1400x850")

        self.root.configure(
            bg="#101820"
        )

        self.create_header()

        self.create_cards()

        self.create_graph_area()

        self.create_bottom_area()

        self.update_dashboard()


    # ========================================================
    # HEADER
    # ========================================================

    def create_header(self):

        header = tk.Frame(
            self.root,
            bg="#17232c",
            height=70
        )

        header.pack(
            fill="x"
        )

        title = tk.Label(
            header,
            text="SMART ENERGY MANAGEMENT SYSTEM",
            font=("Arial", 22, "bold"),
            bg="#17232c",
            fg="white"
        )

        title.pack(
            side="left",
            padx=25,
            pady=18
        )

        self.status_label = tk.Label(
            header,
            text="● SYSTEM ONLINE",
            font=("Arial", 12, "bold"),
            bg="#17232c",
            fg="#00ff88"
        )

        self.status_label.pack(
            side="right",
            padx=25
        )


    # ========================================================
    # CARDS
    # ========================================================

    def create_cards(self):

        card_frame = tk.Frame(
            self.root,
            bg="#101820"
        )

        card_frame.pack(
            fill="x",
            padx=15,
            pady=15
        )

        self.cards = {}

        card_data = [
            ("Daily Energy", "0 kWh"),
            ("Peak Power", "0 kW"),
            ("Energy Saving", "0 %"),
            ("Monthly Energy", "0 kWh"),
            ("Estimated Bill", "₹0"),
            ("Next Hour", "0 kW")
        ]

        for i, (title, value) in enumerate(card_data):

            frame = tk.Frame(
                card_frame,
                bg="#1d2b34",
                width=210,
                height=100
            )

            frame.grid(
                row=0,
                column=i,
                padx=7,
                sticky="nsew"
            )

            card_frame.columnconfigure(
                i,
                weight=1
            )

            tk.Label(
                frame,
                text=title,
                font=("Arial", 11),
                bg="#1d2b34",
                fg="#b8c7d1"
            ).pack(
                pady=(15, 5)
            )

            value_label = tk.Label(
                frame,
                text=value,
                font=("Arial", 20, "bold"),
                bg="#1d2b34",
                fg="white"
            )

            value_label.pack()

            self.cards[title] = value_label


    # ========================================================
    # GRAPH AREA
    # ========================================================

    def create_graph_area(self):

        graph_frame = tk.Frame(
            self.root,
            bg="#101820"
        )

        graph_frame.pack(
            fill="both",
            expand=True,
            padx=15
        )

        self.figure = plt.Figure(
            figsize=(12, 5),
            dpi=100
        )

        self.ax1 = self.figure.add_subplot(
            121
        )

        self.ax2 = self.figure.add_subplot(
            122
        )

        self.canvas = FigureCanvasTkAgg(
            self.figure,
            master=graph_frame
        )

        self.canvas.get_tk_widget().pack(
            fill="both",
            expand=True
        )


    # ========================================================
    # BOTTOM AREA
    # ========================================================

    def create_bottom_area(self):

        bottom = tk.Frame(
            self.root,
            bg="#101820"
        )

        bottom.pack(
            fill="x",
            padx=15,
            pady=10
        )

        # Current Profile
        profile = tk.Frame(
            bottom,
            bg="#1d2b34"
        )

        profile.pack(
            side="left",
            fill="both",
            expand=True,
            padx=5
        )

        tk.Label(
            profile,
            text="CURRENT PROFILE",
            font=("Arial", 13, "bold"),
            bg="#1d2b34",
            fg="white"
        ).pack(
            pady=8
        )

        self.profile_label = tk.Label(
            profile,
            text="Loading...",
            justify="left",
            font=("Arial", 11),
            bg="#1d2b34",
            fg="#d5e0e8"
        )

        self.profile_label.pack(
            pady=5
        )

        # System Status
        system = tk.Frame(
            bottom,
            bg="#1d2b34"
        )

        system.pack(
            side="right",
            fill="both",
            expand=True,
            padx=5
        )

        tk.Label(
            system,
            text="SYSTEM STATUS",
            font=("Arial", 13, "bold"),
            bg="#1d2b34",
            fg="white"
        ).pack(
            pady=8
        )

        self.system_label = tk.Label(
            system,
            text="Sensor       : ONLINE\n"
                 "Database     : ONLINE\n"
                 "ML Model     : READY\n"
                 "Dashboard    : ONLINE",
            justify="left",
            font=("Arial", 11),
            bg="#1d2b34",
            fg="#00ff88"
        )

        self.system_label.pack(
            pady=5
        )


    # ========================================================
    # UPDATE DASHBOARD
    # ========================================================

    def update_dashboard(self):

        try:

            # -----------------------------------------------
            # Cards
            # -----------------------------------------------

            daily = daily_energy()

            peak = peak_power()

            saving = energy_saving_percentage()

            monthly = monthly_energy()

            bill = estimated_bill()

            prediction = next_hour_prediction()

            self.cards[
                "Daily Energy"
            ].config(
                text=f"{daily:.2f} kWh"
            )

            self.cards[
                "Peak Power"
            ].config(
                text=f"{peak:.2f} kW"
            )

            self.cards[
                "Energy Saving"
            ].config(
                text=f"{saving:.1f}%"
            )

            self.cards[
                "Monthly Energy"
            ].config(
                text=f"{monthly:.2f} kWh"
            )

            self.cards[
                "Estimated Bill"
            ].config(
                text=f"₹{bill:.2f}"
            )

            self.cards[
                "Next Hour"
            ].config(
                text=f"{prediction:.2f} kW"
            )

            # -----------------------------------------------
            # Current Profile
            # -----------------------------------------------

            latest = get_latest_data()

            if not latest.empty:

                voltage = latest.iloc[0]["voltage"]

                current = latest.iloc[0]["current_amp"]

                power = latest.iloc[0]["power_kw"]

                pf = latest.iloc[0]["power_factor"]

                frequency = latest.iloc[0]["frequency"]

                profile_text = (
                    f"Voltage       : {voltage:.2f} V\n"
                    f"Current       : {current:.2f} A\n"
                    f"Power         : {power:.2f} kW\n"
                    f"Power Factor  : {pf:.2f}\n"
                    f"Frequency     : {frequency:.2f} Hz"
                )

                self.profile_label.config(
                    text=profile_text
                )

            # -----------------------------------------------
            # Graphs
            # -----------------------------------------------

            self.update_graphs()

        except Exception as error:

            print("Dashboard error:", error)


    # ========================================================
    # GRAPHS
    # ========================================================

    def update_graphs(self):

        self.ax1.clear()

        self.ax2.clear()

        df = get_energy_dataframe()

        # ----------------------------------------------------
        # 24-HOUR POWER GRAPH
        # ----------------------------------------------------

        today = datetime.now().date()

        today_data = df[
            df["timestamp"].dt.date == today
        ]

        if today_data.empty:

            # If today's data is unavailable,
            # show latest 24 records
            today_data = df.tail(24)

        self.ax1.plot(
            today_data["timestamp"],
            today_data["power_kw"],
            marker="o"
        )

        self.ax1.set_title(
            "24-HOUR POWER CONSUMPTION"
        )

        self.ax1.set_xlabel(
            "Time"
        )

        self.ax1.set_ylabel(
            "Power (kW)"
        )

        self.ax1.grid(
            True,
            alpha=0.3
        )

        self.figure.autofmt_xdate()

        # ----------------------------------------------------
        # APPLICATION-WISE ENERGY
        # ----------------------------------------------------

        conn = sqlite3.connect(DB_NAME)

        app_data = pd.read_sql_query("""
            SELECT appliance,
                   SUM(energy_kwh) AS energy
            FROM appliance_data
            GROUP BY appliance
            ORDER BY energy DESC
        """, conn)

        conn.close()

        if not app_data.empty:

            self.ax2.bar(
                app_data["appliance"],
                app_data["energy"]
            )

            self.ax2.set_title(
                "APPLICATION-WISE ENERGY"
            )

            self.ax2.set_xlabel(
                "Application"
            )

            self.ax2.set_ylabel(
                "Energy (kWh)"
            )

            self.ax2.tick_params(
                axis="x",
                rotation=45
            )

        self.figure.tight_layout()

        self.canvas.draw()


# ============================================================
# MAIN PROGRAM
# ============================================================

def main():

    print("=" * 60)

    print(
        "SMART ENERGY MANAGEMENT SYSTEM"
    )

    print("=" * 60)

    # Create database
    create_database()

    # Generate demonstration smart-meter data
    generate_energy_data()

    # Start GUI
    root = tk.Tk()

    app = EnergyDashboard(root)

    root.mainloop()


if __name__ == "__main__":
    main()