# -*- coding: utf-8 -*-
"""app.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1ny7yr6Wb2sgLdGvnwb61o9YohmZSn3NN
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly
import plotly.express as px
from datetime import datetime, timedelta
import sqlite3
import hashlib
import os
from PIL import Image
from io import BytesIO
import base64

# Set page configuration
st.set_page_config(
    page_title="Startive - Smart Savings",
    page_icon="💰",
    layout="wide"
)

# Colors from the logo
PRIMARY_COLOR = "#8E85A6"  # Light purple
SECONDARY_COLOR = "#191525"  # Dark purple/black
BACKGROUND_COLOR = "#F9F7FC"  # Very light purple
TEXT_COLOR = "#3A3042"  # Dark purple-gray

# Create Startive logo - simple SVG implementation
def get_startive_logo():
    logo_svg = f"""
    <svg width="200" height="60" viewBox="0 0 400 120">
        <path d="M180 10 L280 30 L300 90 L200 110 L100 80 L80 40 Z" fill="{PRIMARY_COLOR}" fill-opacity="0.5"/>
        <text x="110" y="70" font-family="Arial, sans-serif" font-weight="bold" font-size="36" fill="{SECONDARY_COLOR}">STARTIVE</text>
    </svg>
    """
    return logo_svg

# Database setup
def init_db():
    conn = sqlite3.connect('startive.db')
    c = conn.cursor()

    # Create users table
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        subscription_tier TEXT DEFAULT 'basic',
        risk_preference TEXT DEFAULT 'moderate',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create transactions table
    c.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        category TEXT NOT NULL,
        description TEXT,
        transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        roundup_amount REAL DEFAULT 0.0,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # Create savings table
    c.execute('''
    CREATE TABLE IF NOT EXISTS savings (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        source TEXT,
        saving_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        allocation_type TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # Create goals table
    c.execute('''
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        target_amount REAL NOT NULL,
        current_amount REAL DEFAULT 0.0,
        deadline TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    conn.commit()
    conn.close()

# Helper functions
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(stored_hash, provided_password):
    return stored_hash == hashlib.sha256(provided_password.encode()).hexdigest()

def register_user(username, email, password):
    conn = sqlite3.connect('startive.db')
    c = conn.cursor()

    try:
        password_hash = hash_password(password)
        c.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                 (username, email, password_hash))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def authenticate_user(email, password):
    conn = sqlite3.connect('startive.db')
    c = conn.cursor()

    c.execute("SELECT id, username, password_hash, subscription_tier, risk_preference FROM users WHERE email = ?", (email,))
    user = c.fetchone()
    conn.close()

    if user and verify_password(user[2], password):
        return {"id": user[0], "username": user[1], "subscription_tier": user[3], "risk_preference": user[4]}
    return None

def add_transaction(user_id, amount, category, description):
    conn = sqlite3.connect('startive.db')
    c = conn.cursor()

    # Calculate roundup amount
    decimal_part = amount - int(amount)
    roundup = 0.0
    if decimal_part > 0:
        roundup = round(1 - decimal_part, 2)

    c.execute("""
    INSERT INTO transactions (user_id, amount, category, description, roundup_amount)
    VALUES (?, ?, ?, ?, ?)
    """, (user_id, amount, category, description, roundup))

    # Add roundup to savings if > 0
    if roundup > 0:
        risk_preference = get_user_risk_preference(user_id)
        allocation = determine_allocation(risk_preference)

        c.execute("""
        INSERT INTO savings (user_id, amount, source, allocation_type)
        VALUES (?, ?, ?, ?)
        """, (user_id, roundup, "roundup", allocation))

    conn.commit()
    conn.close()

def get_user_risk_preference(user_id):
    conn = sqlite3.connect('startive.db')
    c = conn.cursor()

    c.execute("SELECT risk_preference FROM users WHERE id = ?", (user_id,))
    risk = c.fetchone()[0]

    conn.close()
    return risk

def determine_allocation(risk_preference):
    """Determine allocation type based on user risk preference"""
    if risk_preference == 'conservative':
        options = ['high-yield savings'] * 7 + ['ETF'] * 3
    elif risk_preference == 'moderate':
        options = ['high-yield savings'] * 5 + ['ETF'] * 4 + ['crypto'] * 1
    elif risk_preference == 'aggressive':
        options = ['high-yield savings'] * 3 + ['ETF'] * 5 + ['crypto'] * 2
    else:
        options = ['high-yield savings'] * 5 + ['ETF'] * 5

    return np.random.choice(options)

def get_transactions(user_id, limit=5):
    conn = sqlite3.connect('startive.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
    SELECT id, amount, category, description, transaction_date, roundup_amount
    FROM transactions
    WHERE user_id = ?
    ORDER BY transaction_date DESC
    LIMIT ?
    """, (user_id, limit))

    transactions = [dict(row) for row in c.fetchall()]
    conn.close()

    return transactions

def get_total_savings(user_id):
    conn = sqlite3.connect('startive.db')
    c = conn.cursor()

    c.execute("SELECT SUM(amount) FROM savings WHERE user_id = ?", (user_id,))
    total = c.fetchone()[0]

    conn.close()
    return total or 0

def get_savings_by_date(user_id):
    conn = sqlite3.connect('startive.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
    SELECT date(saving_date) as date, SUM(amount) as total
    FROM savings
    WHERE user_id = ?
    GROUP BY date(saving_date)
    ORDER BY date(saving_date)
    """, (user_id,))

    savings = [dict(row) for row in c.fetchall()]
    conn.close()

    return savings

def get_allocation_data(user_id):
    conn = sqlite3.connect('startive.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
    SELECT allocation_type, SUM(amount) as total
    FROM savings
    WHERE user_id = ?
    GROUP BY allocation_type
    """, (user_id,))

    allocations = [dict(row) for row in c.fetchall()]
    conn.close()

    return allocations

def get_goals(user_id):
    conn = sqlite3.connect('startive.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
    SELECT id, name, target_amount, current_amount, deadline
    FROM goals
    WHERE user_id = ?
    """, (user_id,))

    goals = [dict(row) for row in c.fetchall()]

    # Calculate progress for each goal
    for goal in goals:
        if goal['target_amount'] > 0:
            goal['progress'] = (goal['current_amount'] / goal['target_amount']) * 100
        else:
            goal['progress'] = 0

    conn.close()
    return goals

def add_goal(user_id, name, target_amount, deadline=None):
    conn = sqlite3.connect('startive.db')
    c = conn.cursor()

    c.execute("""
    INSERT INTO goals (user_id, name, target_amount, deadline)
    VALUES (?, ?, ?, ?)
    """, (user_id, name, target_amount, deadline))

    conn.commit()
    conn.close()

def update_risk_preference(user_id, risk_preference):
    conn = sqlite3.connect('startive.db')
    c = conn.cursor()

    c.execute("UPDATE users SET risk_preference = ? WHERE id = ?", (risk_preference, user_id))

    conn.commit()
    conn.close()

def update_subscription(user_id, tier):
    conn = sqlite3.connect('startive.db')
    c = conn.cursor()

    c.execute("UPDATE users SET subscription_tier = ? WHERE id = ?", (tier, user_id))

    conn.commit()
    conn.close()

def ai_chatbot_response(question, user_id):
    """Simple rule-based AI chatbot responses"""
    question = question.lower()

    if 'how much' in question and ('save' in question or 'saving' in question):
        # In a real app, this would analyze transaction patterns
        total_savings = get_total_savings(user_id)
        return f"Based on your recent transactions, you can safely save approximately ${total_savings * 0.1:.2f} per month."

    elif 'investment' in question or 'invest' in question:
        risk_preference = get_user_risk_preference(user_id)
        if risk_preference == 'conservative':
            return "With your conservative risk profile, I recommend focusing on high-yield savings accounts and stable ETFs."
        elif risk_preference == 'moderate':
            return "With your moderate risk profile, a balanced approach of ETFs and some high-yield savings would work well."
        else:
            return "With your aggressive risk profile, you might consider a higher allocation to ETFs and some cryptocurrency exposure."

    elif 'goal' in question:
        goals = get_goals(user_id)
        if not goals:
            return "You haven't set any financial goals yet. Would you like to create one?"

        closest_goal = sorted(goals, key=lambda g: g['progress'])[0]
        return f"You're making progress on your '{closest_goal['name']}' goal! You're {closest_goal['progress']:.1f}% of the way there."

    else:
        return "I'm here to help with your financial questions. You can ask about savings recommendations, investment strategies, your goals, or roundup savings."

# Alternative implementation for KMeans clustering
def analyze_spending(transactions):
    """Simple spending analysis without sklearn dependency"""
    if not transactions:
        return "No spending data available."

    # Convert to DataFrame
    df = pd.DataFrame(transactions)

    # Basic statistics
    total_spent = df['amount'].sum()
    avg_transaction = df['amount'].mean()
    highest_category = df.groupby('category')['amount'].sum().idxmax()

    # Simple spending clusters (low, medium, high) without KMeans
    df['amount_percentile'] = df['amount'].rank(pct=True)

    # Assign clusters based on percentiles instead of KMeans
    conditions = [
        df['amount_percentile'] < 0.33,
        (df['amount_percentile'] >= 0.33) & (df['amount_percentile'] < 0.67),
        df['amount_percentile'] >= 0.67
    ]
    values = ['low', 'medium', 'high']
    df['spending_cluster'] = np.select(conditions, values)

    return {
        'data': df,
        'summary': {
            'total_spent': total_spent,
            'avg_transaction': avg_transaction,
            'highest_category': highest_category
        }
    }

# Initialize database
init_db()

# Session state initialization
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if 'user' not in st.session_state:
    st.session_state.user = None

if 'page' not in st.session_state:
    st.session_state.page = 'login'

# Custom styling
st.markdown(f"""
<style>
    .stApp {{
        background-color: {BACKGROUND_COLOR};
    }}
    .stButton button {{
        background-color: {PRIMARY_COLOR};
        color: white;
    }}
    .stProgress > div > div {{
        background-color: {PRIMARY_COLOR};
    }}
    h1, h2, h3 {{
        color: {SECONDARY_COLOR};
    }}
    .goal-card {{
        background-color: white;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }}
    .dashboard-stats {{
        background-color: {PRIMARY_COLOR};
        color: white;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
    }}
</style>
""", unsafe_allow_html=True)

# Display logo
st.markdown(f'<div style="text-align: center;">{get_startive_logo()}</div>', unsafe_allow_html=True)

# Main application logic
if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        st.subheader("Login")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")

        if st.button("Login", key="login_button"):
            user = authenticate_user(email, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.session_state.page = 'dashboard'
                st.rerun()
            else:
                st.error("Invalid email or password")

    with tab2:
        st.subheader("Register")
        username = st.text_input("Username", key="reg_username")
        email = st.text_input("Email", key="reg_email")
        password = st.text_input("Password", type="password", key="reg_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm")

        if st.button("Register", key="register_button"):
            if password != confirm_password:
                st.error("Passwords do not match!")
            elif not username or not email or not password:
                st.error("All fields are required!")
            else:
                if register_user(username, email, password):
                    st.success("Registration successful! Please login.")
                    st.session_state.page = 'login'
                else:
                    st.error("Username or email already exists!")
else:
    # Sidebar navigation
    st.sidebar.title(f"Hello, {st.session_state.user['username']}!")
    page = st.sidebar.radio("Navigation", ["Dashboard", "Transactions", "Savings", "Goals", "AI Advisor", "Profile", "Logout"])

    if page == "Logout":
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.page = 'login'
        st.rerun()

    elif page == "Dashboard":
        st.title("Dashboard")

        # Stats summary
        total_savings = get_total_savings(st.session_state.user['id'])

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Savings", f"${total_savings:.2f}")
        with col2:
            st.metric("Subscription", st.session_state.user["subscription_tier"].capitalize())
        with col3:
            st.metric("Risk Profile", st.session_state.user["risk_preference"].capitalize())

        # Savings chart
        savings_data = get_savings_by_date(st.session_state.user['id'])
        if savings_data:
            df = pd.DataFrame(savings_data)
            df['cumulative'] = df['total'].cumsum()

            st.subheader("Savings Growth")
            try:
                fig = px.line(df, x='date', y='cumulative', title='Cumulative Savings Over Time')
                fig.update_layout(xaxis_title='Date', yaxis_title='Amount ($)')
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Could not display chart: {e}")
                # Fallback to simple table
                st.dataframe(df)
        else:
            st.info("Start saving to see your progress!")

        # Recent transactions
        st.subheader("Recent Transactions")
        transactions = get_transactions(st.session_state.user['id'])
        if transactions:
            df = pd.DataFrame(transactions)
            st.dataframe(df[['transaction_date', 'category', 'description', 'amount', 'roundup_amount']])
        else:
            st.info("No transactions yet. Add one below!")

        # Goals
        st.subheader("Financial Goals")
        goals = get_goals(st.session_state.user['id'])
        if goals:
            for goal in goals:
                with st.expander(f"{goal['name']} - ${goal['current_amount']:.2f} / ${goal['target_amount']:.2f}"):
                    st.progress(min(goal['progress'] / 100, 1.0))
                    st.text(f"Progress: {goal['progress']:.1f}%")
        else:
            st.info("No goals set. Create one in the Goals section!")

    elif page == "Transactions":
        st.title("Transactions")

        # Add transaction form
        st.subheader("Add New Transaction")
        col1, col2 = st.columns(2)
        with col1:
            amount = st.number_input("Amount ($)", min_value=0.01, step=0.01)
            category = st.selectbox("Category", ["Groceries", "Dining", "Entertainment", "Utilities", "Rent", "Transportation", "Shopping", "Other"])
        with col2:
            description = st.text_input("Description")
            submitted = st.button("Add Transaction")

        if submitted:
            add_transaction(st.session_state.user['id'], amount, category, description)
            st.success("Transaction added successfully!")
            st.rerun()

        # Show all transactions
        st.subheader("All Transactions")
        transactions = get_transactions(st.session_state.user['id'], limit=100)
        if transactions:
            df = pd.DataFrame(transactions)
            st.dataframe(df[['transaction_date', 'category', 'description', 'amount', 'roundup_amount']])

            # Spending analysis
            st.subheader("Spending Analysis")
            analysis = analyze_spending(transactions)
            if isinstance(analysis, dict):
                if 'summary' in analysis:
                    summary = analysis['summary']
                    st.info(f"Total spent: ${summary['total_spent']:.2f} | Average transaction: ${summary['avg_transaction']:.2f} | Highest spending category: {summary['highest_category']}")

                if 'data' in analysis and isinstance(analysis['data'], pd.DataFrame):
                    # Display spending by category
                    try:
                        category_data = analysis['data'].groupby('category')['amount'].sum().reset_index()
                        fig = px.pie(category_data, values='amount', names='category', title='Spending by Category')
                        st.plotly_chart(fig, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Could not generate category chart: {e}")
                        st.dataframe(category_data)
            else:
                st.info(analysis)  # If it's just a string message
        else:
            st.info("No transactions yet!")

    elif page == "Savings":
        st.title("Savings & Investments")

        # Total savings
        total_savings = get_total_savings(st.session_state.user['id'])
        st.metric("Total Savings", f"${total_savings:.2f}")

        # Savings allocation
        allocation_data = get_allocation_data(st.session_state.user['id'])
        if allocation_data:
            st.subheader("Investment Allocation")
            df = pd.DataFrame(allocation_data)
            try:
                fig = px.pie(df, values='total', names='allocation_type', title='Investment Allocation')
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Could not display chart: {e}")
                # Fallback to table
                st.dataframe(df)
        else:
            st.info("No savings allocations yet. Add transactions to generate round-ups!")

        # Savings history chart
        savings_data = get_savings_by_date(st.session_state.user['id'])
        if savings_data:
            st.subheader("Savings History")
            df = pd.DataFrame(savings_data)
            try:
                fig = px.bar(df, x='date', y='total', title='Daily Savings')
                fig.update_layout(xaxis_title='Date', yaxis_title='Amount ($)')
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Could not display chart: {e}")
                st.dataframe(df)

    elif page == "Goals":
        st.title("Financial Goals")

        # Add goal form
        st.subheader("Create New Goal")
        col1, col2 = st.columns(2)
        with col1:
            goal_name = st.text_input("Goal Name")
            target_amount = st.number_input("Target Amount ($)", min_value=1.0, step=10.0)
        with col2:
            deadline = st.date_input("Deadline (Optional)")
            submitted = st.button("Add Goal")

        if submitted:
            if not goal_name:
                st.error("Goal name is required!")
            else:
                deadline_str = deadline.strftime("%Y-%m-%d") if deadline else None
                add_goal(st.session_state.user['id'], goal_name, target_amount, deadline_str)
                st.success("Goal added successfully!")
                st.rerun()

        # Show all goals
        st.subheader("Your Goals")
        goals = get_goals(st.session_state.user['id'])
        if goals:
            for goal in goals:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(f"{goal['name']}")
                    st.progress(min(goal['progress'] / 100, 1.0))
                    st.text(f"${goal['current_amount']:.2f} / ${goal['target_amount']:.2f} ({goal['progress']:.1f}%)")
                with col2:
                    if goal.get('deadline'):
                        st.text(f"Deadline: {goal['deadline']}")
        else:
            st.info("No goals yet!")

    elif page == "AI Advisor":
        st.title("AI Financial Advisor")

        # Simple chatbot interface
        question = st.text_input("Ask a financial question:", placeholder="E.g., How much can I save this month?")

        if question:
            response = ai_chatbot_response(question, st.session_state.user['id'])
            st.info(response)

        # Sample questions
        st.subheader("Sample Questions")
        sample_questions = [
            "How much can I save this month?",
            "What investment strategy would you recommend?",
            "How am I doing on my goals?"
        ]

        for q in sample_questions:
            if st.button(q):
                response = ai_chatbot_response(q, st.session_state.user['id'])
                st.info(response)

    elif page == "Profile":
        st.title("Account Settings")

        # Profile tabs
        tab1, tab2 = st.tabs(["Risk Profile", "Subscription"])

        with tab1:
            st.subheader("Investment Risk Profile")
            current_risk = st.session_state.user['risk_preference']
            risk_options = ["conservative", "moderate", "aggressive"]
            risk_descriptions = {
                "conservative": "Lower risk, steady returns. Focus on high-yield savings and stable ETFs.",
                "moderate": "Balanced risk and returns. Mix of savings, ETFs, and minimal crypto.",
                "aggressive": "Higher risk, potential for higher returns. More allocation to ETFs and crypto."
            }

            selected_risk = st.radio("Select your risk preference:", risk_options, index=risk_options.index(current_risk))
            st.markdown(f"**{risk_descriptions[selected_risk]}**")

            if st.button("Update Risk Profile") and selected_risk != current_risk:
                update_risk_preference(st.session_state.user['id'], selected_risk)
                st.session_state.user['risk_preference'] = selected_risk
                st.success("Risk profile updated successfully!")
                st.rerun()

        with tab2:
            st.subheader("Subscription Plan")
            current_tier = st.session_state.user['subscription_tier']

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### Basic")
                st.markdown("- Round-up savings")
                st.markdown("- AI financial assistant")
                st.markdown("- Basic investment options")
                st.markdown("- $5.99/month")
                if current_tier == "basic":
                    st.info("Current Plan")
                else:
                    if st.button("Downgrade to Basic"):
                        update_subscription(st.session_state.user['id'], "basic")
                        st.session_state.user['subscription_tier'] = "basic"
                        st.success("Subscription updated successfully!")
                        st.rerun()

            with col2:
                st.markdown("### Elite")
                st.markdown("- Everything in Basic")
                st.markdown("- Human advisor consultations")
                st.markdown("- Advanced investment options")
                st.markdown("- Priority customer support")
                st.markdown("- $14.99/month")
                if current_tier == "elite":
                    st.info("Current Plan")
                else:
                    if st.button("Upgrade to Elite"):
                        update_subscription(st.session_state.user['id'], "elite")
                        st.session_state.user['subscription_tier'] = "elite"
                        st.success("Subscription updated successfully!")
                        st.rerun()

# Only show welcome page if not logged in
if not st.session_state.logged_in:
    st.title("Welcome to Startive")

    # Demonstrate basic functionality without requiring login
    st.markdown("""
    ### Smart Savings Made Simple
    Startive helps you save money automatically through:
    - Round-up transactions
    - Smart investment allocations
    - Goal tracking
    - AI-powered financial advice

    Register or login to start your saving journey today!
    """)

    # Sample data visualization that doesn't depend on sklearn
    st.subheader("How Startive Works")

    # Sample data
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    savings = [50, 120, 200, 280, 350, 430]

    # Create sample chart
    try:
        sample_df = pd.DataFrame({"Month": months, "Savings": savings})
        fig = px.line(sample_df, x="Month", y="Savings", title="Example Savings Growth")
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Could not display sample chart: {e}")
        # Fallback to text
        st.write("Example savings growth: Starting with $50 in January, growing to $430 by June")
