from flask import Flask, render_template, request, redirect, flash, session, url_for
import mysql.connector
from flask_bcrypt import Bcrypt
from functools import wraps
from datetime import datetime, timedelta
from config import MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_NAME, SECRET_KEY
import random

# Initialize the Flask app and MySQL connection
app = Flask(__name__)
app.secret_key = SECRET_KEY
bcrypt = Bcrypt(app)

def get_db_connection():
    return mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_NAME
    )

####################################################################################################

# Define Login Required
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # if 'email' not in session:
        if 'user_email' not in session:
            flash('You must be logged in to view this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Homepage
@app.route('/')
def home():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM flight")
    flights = cursor.fetchall()

    cursor.execute("SELECT DISTINCT departure_airport FROM flight")
    departure_airports = cursor.fetchall()

    cursor.execute("SELECT DISTINCT arrival_airport FROM flight")
    arrival_airports = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('home.html', flights=flights, departure_airports=departure_airports, arrival_airports=arrival_airports)

# Test to see if the database connection is working
@app.route('/test')
def test():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES;")
    tables = cursor.fetchall()
    cursor.close()
    conn.close()
    # return {"tables": tables}
    return {"tables": [table[0] for table in tables]}

# Test feature to show flight Details
@app.route('/flights/<int:flight_num>')
def flight_details(flight_num):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM flight WHERE flight_num = %s", (flight_num,))
    flight = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if flight is None:
        flash("Flight not found.")
        return redirect(url_for('home'))
    
    return render_template('flight_details.html', flight=flight)

# Search Flights
@app.route('/search', methods=['GET'])
def search_flights():
    source = request.args.get('source')
    destination = request.args.get('destination')
    date = request.args.get('date')

    # Error handling for missing fields
    if not source or not destination or not date:
        flash('All fields are required to search flights.', 'danger')
        return redirect(url_for('home'))

    # Get the logged-in user's email (if any)
    user_email = session.get('user_email')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        if user_email:
            # Check if the user is a booking agent
            cursor.execute("SELECT airline_name FROM booking_agent_work_for WHERE email = %s", (user_email,))
            booking_agent = cursor.fetchone()

            if booking_agent:
                # Booking agent can only see flights from their airline
                airline_name = booking_agent['airline_name']
                query = """
                    SELECT * FROM flight
                    WHERE departure_airport = %s 
                      AND arrival_airport = %s 
                      AND DATE(departure_time) = %s
                      AND airline_name = %s
                """
                cursor.execute(query, (source, destination, date, airline_name))
            else:
                # Customers can see flights from all airlines
                query = """
                    SELECT * FROM flight
                    WHERE departure_airport = %s 
                      AND arrival_airport = %s 
                      AND DATE(departure_time) = %s
                """
                cursor.execute(query, (source, destination, date))
        else:
            # Non-logged-in users can see flights from all airlines
            query = """
                SELECT * FROM flight
                WHERE departure_airport = %s 
                  AND arrival_airport = %s 
                  AND DATE(departure_time) = %s
            """
            cursor.execute(query, (source, destination, date))

        flights = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return render_template('search_results.html', flights=flights, search_failed=(len(flights) == 0))

# Signup
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        role = request.form['role']
        email = request.form['email']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the email already exists in the database for customer, booking agent, or airline staff
        if role == 'customer':
            cursor.execute("SELECT * FROM customer WHERE email = %s", (email,))
            user = cursor.fetchone()
        elif role == 'booking_agent':
            cursor.execute("SELECT * FROM booking_agent WHERE email = %s", (email,))
            user = cursor.fetchone()
        elif role == 'airline_staff':
            cursor.execute("SELECT * FROM airline_staff WHERE username = %s", (email,)) 
            user = cursor.fetchone()
        if user:
            flash('Email is already in use. Please choose another one.', 'danger')
            return redirect(url_for('signup'))
        
        # Check if the airline name is valid
        if role == 'airline_staff':
            airline_name = request.form['airline_name']
            cursor.execute("SELECT * FROM airline WHERE airline_name = %s", (airline_name,))
            airline = cursor.fetchone()
            if not airline:
                flash('Invalid airline name. Please choose a valid airline.', 'danger')
                return redirect(url_for('signup'))

        # If role is customer, save the data in the customer table
        if role == 'customer':
            name = request.form['name']
            building_number = request.form['building_number']
            street = request.form['street']
            city = request.form['city']
            state = request.form['state']
            phone_number = request.form['phone_number']
            passport_number = request.form['passport_number']
            passport_expiration = request.form['passport_expiration']
            passport_country = request.form['passport_country']
            date_of_birth = request.form['date_of_birth']
            cursor.execute(
                """
                INSERT INTO customer (email, name, password, building_number, street, city, state, 
                phone_number, passport_number, passport_expiration, passport_country, date_of_birth)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (email, name, password, building_number, street, city, state, phone_number, passport_number,
                 passport_expiration, passport_country, date_of_birth)
            )
        elif role == 'booking_agent':
            booking_agent_id = request.form['booking_agent_id']
            cursor.execute(
                "INSERT INTO booking_agent (email, password, booking_agent_id) VALUES (%s, %s, %s)",
                (email, password, booking_agent_id)
            )
        elif role == 'airline_staff':
            first_name = request.form['first_name']
            last_name = request.form['last_name']
            airline_name = request.form['airline_name']
            date_of_birth = request.form['date_of_birth']
            cursor.execute(
                """
                INSERT INTO airline_staff (username, password, first_name, last_name, airline_name, date_of_birth)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (email, password, first_name, last_name, airline_name, date_of_birth)
            )

        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('signup.html')

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form['role']
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        user = None
        if role == 'customer':
            cursor.execute("SELECT * FROM customer WHERE email = %s", (email,))
        elif role == 'booking_agent':
            cursor.execute("SELECT * FROM booking_agent WHERE email = %s", (email,))
        elif role == 'airline_staff':
            cursor.execute("SELECT * FROM airline_staff WHERE username = %s", (email,))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user and bcrypt.check_password_hash(user['password'], password):
            # Set session variables
            session['role'] = role
            session['user_email'] = user['email'] if role != 'airline_staff' else user['username']

            # Store airline_name in session if the user is an airline staff
            if role == 'airline_staff':
                session['airline_name'] = user['airline_name']

            flash(f'Logged in as {role.capitalize()}!', 'success')

            # Redirect based on user role
            if role == 'customer':
                return redirect(url_for('customer_dashboard'))
            elif role == 'booking_agent':
                return redirect(url_for('booking_agent_dashboard'))
            elif role == 'airline_staff':
                return redirect(url_for('airline_staff_dashboard'))
        else:
            flash('Invalid login credentials. Please try again.', 'danger')
    
    return render_template('login.html')

# Logout
@app.route('/logout')
def logout():
    # session.clear()
    session.pop('user_email', None)
    session.pop('role', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))  # Redirects directly to login page

####################################################################################################

# Customer Dashboard
@app.route('/customer_dashboard', methods=['GET', 'POST'])
@login_required
def customer_dashboard():
    user_email = session['user_email']
    role = session['role']

    if role != 'customer':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try: 
        cursor.execute("SELECT DISTINCT departure_airport FROM flight")
        departure_airports = cursor.fetchall()

        cursor.execute("SELECT DISTINCT arrival_airport FROM flight")
        arrival_airports = cursor.fetchall()

        cursor.execute("SELECT * FROM customer WHERE email = %s", (user_email,))
        customer_info = cursor.fetchone()

        # Fetch data for total spending in the last year and last 6 months
        cursor.execute("""
            SELECT DATE_FORMAT(p.purchase_date, '%Y-%m') AS month, 
                   SUM(f.price) AS total_spent
            FROM purchases p
            JOIN ticket t ON p.ticket_id = t.ticket_id
            JOIN flight f ON t.flight_num = f.flight_num
            WHERE p.customer_email = %s AND p.purchase_date >= CURDATE() - INTERVAL 6 MONTH
            GROUP BY month
            ORDER BY month;
        """, (user_email,))
        last_six_months_spending = cursor.fetchall()

        cursor.execute("""
            SELECT SUM(f.price) AS total_spent
            FROM purchases p
            JOIN ticket t ON p.ticket_id = t.ticket_id
            JOIN flight f ON t.flight_num = f.flight_num
            WHERE p.customer_email = %s AND p.purchase_date >= CURDATE() - INTERVAL 1 YEAR;
        """, (user_email,))
        total_spent_last_year = cursor.fetchone()['total_spent'] or 0

        total_spent_last_six_months = sum(entry['total_spent'] or 0 for entry in last_six_months_spending)

        # Handle POST request for custom date range
        start_date, end_date = None, None
        monthly_spending = []
        total_spent_range = 0

        # Handle POST request for custom date range
        start_date, end_date = None, None
        monthly_spending = []
        total_spent_range = 0

        if request.method == 'POST':
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            cursor.execute("""
                SELECT DATE_FORMAT(p.purchase_date, '%Y-%m') AS month,
                       SUM(f.price) AS total_spent
                FROM purchases p
                JOIN ticket t ON p.ticket_id = t.ticket_id
                JOIN flight f ON t.flight_num = f.flight_num
                WHERE p.customer_email = %s AND p.purchase_date BETWEEN %s AND %s
                GROUP BY month
                ORDER BY month;
            """, (user_email, start_date, end_date))
            monthly_spending = cursor.fetchall()
            total_spent_range = sum(entry['total_spent'] or 0 for entry in monthly_spending)

        ############################

        # Get customer information
        cursor.execute("SELECT * FROM customer WHERE email = %s", (user_email,))
        customer_info = cursor.fetchone()

        # Get upcoming flights for the customer
        cursor.execute("""
            SELECT f.airline_name, f.flight_num, f.departure_time, f.arrival_time, f.departure_airport, 
                       f.arrival_airport, f.status, p.purchase_date, f.price
            FROM flight f
            JOIN ticket t ON f.flight_num = t.flight_num AND f.airline_name = t.airline_name
            JOIN purchases p ON t.ticket_id = p.ticket_id
            WHERE p.customer_email = %s AND f.status = 'upcoming'
        """, (user_email,))
        # SELECT flight_num FROM flight WHERE departure_time >= NOW()
        upcoming_flights = cursor.fetchall()

        # Get booking history
        cursor.execute("""
            SELECT f.airline_name, f.flight_num, f.departure_time, f.arrival_time, f.departure_airport, 
                       f.arrival_airport, f.status, p.purchase_date, f.price
            FROM flight f
            JOIN ticket t ON f.flight_num = t.flight_num AND f.airline_name = t.airline_name
            JOIN purchases p ON t.ticket_id = p.ticket_id
            WHERE p.customer_email = %s AND f.status != 'upcoming'
        """, (user_email,))     
        # SELECT flight_num FROM flight WHERE departure_time < NOW()
        booking_history = cursor.fetchall()
    finally: 
        cursor.close()
        conn.close()

    return render_template('customer_dashboard.html', 
                           user_email=user_email, customer_info=customer_info, 
                           upcoming_flights=upcoming_flights, booking_history=booking_history, 
                           departure_airports=departure_airports, arrival_airports=arrival_airports,
                           total_spent_last_six_months=total_spent_last_six_months,
                           total_spent_last_year=total_spent_last_year,
                           last_six_months_spending=last_six_months_spending,
                           monthly_spending=monthly_spending,
                           total_spent_range=total_spent_range,
                           start_date=start_date, end_date=end_date)

# Customer Profile
@app.route('/profile')
@login_required
def profile():
    user_email = session['user_email']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try: 
        query = """
            SELECT name, email, date_of_birth, passport_number, 
                passport_expiration, phone_number, 
                CONCAT(building_number, ' ', street, ', ', city, ', ', state) AS address,
                passport_country
            FROM Customer
            WHERE email = %s
        """
        cursor.execute(query, (user_email,))
        user_details = cursor.fetchone()
        if not user_details:
            flash("Profile details not found. Please contact support.", "danger")
            return redirect(url_for('customer_dashboard'))
    finally:
        cursor.close()
        conn.close()
    return render_template('profile.html', user_details=user_details)

# Customer Purchase Tickets
@app.route('/purchase_ticket', methods=['POST'])
@login_required
def purchase_ticket():
    flight_num = request.form['flight_num']  # Passed from the form
    user_email = session['user_email']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Find an available ticket for the selected flight
        query = """
            SELECT t.ticket_id 
            FROM ticket t
            LEFT JOIN purchases p ON t.ticket_id = p.ticket_id
            WHERE t.flight_num = %s AND p.ticket_id IS NULL
            LIMIT 1;
        """
        cursor.execute(query, (flight_num,))
        available_ticket = cursor.fetchone()

        if not available_ticket:
            flash("No tickets are available for this flight.", "danger")
            return redirect(url_for('customer_dashboard'))

        # Reserve the ticket and log the purchase
        ticket_id = available_ticket['ticket_id']
        purchase_query = """
            INSERT INTO purchases (ticket_id, customer_email, purchase_date)
            VALUES (%s, %s, CURDATE());
        """
        cursor.execute(purchase_query, (ticket_id, user_email))
        conn.commit()
        flash("Ticket purchased successfully!", "success")
        return redirect(url_for('customer_dashboard'))

    except Exception as e:
        conn.rollback()
        flash(f"An error occurred: {e}", "danger")
        return redirect(url_for('customer_dashboard'))
    finally:
        cursor.close()
        conn.close()

# Customer Track Spending
@app.route('/track_spending', methods=['GET', 'POST'])
@login_required
def track_spending():
    user_email = session['user_email']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Default to past year
        query = """
            SELECT DATE_FORMAT(purchase_date, '%Y-%m') AS month, SUM(price) AS total
            FROM purchases
            JOIN ticket ON purchases.ticket_id = ticket.ticket_id
            WHERE purchases.customer_email = %s AND purchase_date >= DATE_SUB(NOW(), INTERVAL 1 YEAR)
            GROUP BY month
            ORDER BY month
        """
        cursor.execute(query, (user_email,))
        spending_data = cursor.fetchall()
        months = [row['month'] for row in spending_data]
        spending = [row['total'] for row in spending_data]
    finally:
        cursor.close()
        conn.close()

    return render_template('spending.html', months=months, spending=spending)

####################################################################################################

# Booking Agent
@app.route('/booking_agent_dashboard', methods=['GET', 'POST'])
@login_required
def booking_agent_dashboard():
    user_email = session['user_email']
    role = session.get('role')

    if role != 'booking_agent':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get the booking agent ID based on the logged-in agent's email
    cursor.execute("SELECT booking_agent_id FROM booking_agent WHERE email = %s", (user_email,))
    booking_agent = cursor.fetchone()
    if not booking_agent:
        flash('Booking agent ID not found. Please contact support.', 'danger')
        return redirect(url_for('home'))
    booking_agent_id = booking_agent['booking_agent_id']
    # Get the date 30 days ago
    thirty_days_ago = datetime.now() - timedelta(days=30)
    thirty_days_ago_str = thirty_days_ago.strftime('%Y-%m-%d')

    try:
        cursor.execute("SELECT DISTINCT departure_airport FROM flight")
        departure_airports = cursor.fetchall()

        cursor.execute("SELECT DISTINCT arrival_airport FROM flight")
        arrival_airports = cursor.fetchall()

        # Retrieve the airline associated with the booking agent from booking_agent_work_for
        cursor.execute("""
            SELECT airline_name FROM booking_agent_work_for 
            WHERE email = %s
        """, (user_email,))
        agent_airline = cursor.fetchone()

        if not agent_airline:
            flash('No airline association found for this booking agent.', 'danger')
            return redirect(url_for('home'))

        airline_name = agent_airline['airline_name']

        # Fetch upcoming flights booked for customers by this booking agent's airline
        cursor.execute("""
            SELECT f.airline_name, f.flight_num, f.departure_time, f.arrival_time, 
                   f.departure_airport, f.arrival_airport, f.price, f.status, p.purchase_date, c.email AS customer_email
            FROM flight f
            JOIN ticket t ON f.flight_num = t.flight_num AND f.airline_name = t.airline_name
            JOIN purchases p ON t.ticket_id = p.ticket_id
            JOIN customer c ON p.customer_email = c.email
            JOIN booking_agent b ON p.booking_agent_id = b.booking_agent_id
            WHERE f.status = 'upcoming' AND f.airline_name = %s AND p.booking_agent_id = b.booking_agent_id;
        """, (airline_name,))
        upcoming_flights = cursor.fetchall()

        ############################ Agent commission
        # Default values for custom variables
        custom_commission = 0
        custom_tickets_sold = 0
        custom_avg_commission = 0

        # Query to get commission, number of tickets sold, and avg commission for last 30 days
        cursor.execute("""
            SELECT 
                SUM(f.price * 0.05) AS total_commission, 
                COUNT(p.ticket_id) AS total_tickets_sold,
                AVG(f.price * 0.05) AS avg_commission_per_ticket
            FROM purchases p
            JOIN ticket t ON p.ticket_id = t.ticket_id
            JOIN flight f ON t.flight_num = f.flight_num AND t.airline_name = f.airline_name
            WHERE p.booking_agent_id = %s 
                AND p.purchase_date >= CURDATE() - INTERVAL 30 DAY;
        """, (booking_agent_id,))
        
        data = cursor.fetchone()
        total_commission = data['total_commission'] if data['total_commission'] else 0
        total_tickets_sold = data['total_tickets_sold'] if data['total_tickets_sold'] else 0
        avg_commission_per_ticket = data['avg_commission_per_ticket'] if data['avg_commission_per_ticket'] else 0
        avg_commission_per_ticket = round(avg_commission_per_ticket, 2)

        # Handle custom date range if submitted
        if request.method == 'POST':
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            
            # Query for custom date range
            cursor.execute("""
                SELECT SUM(f.price * 0.05) AS total_commission, 
                    COUNT(p.ticket_id) AS total_tickets_sold,
                    AVG(f.price * 0.05) AS avg_commission_per_ticket
                FROM purchases p
                JOIN ticket t ON p.ticket_id = t.ticket_id
                JOIN flight f ON t.flight_num = f.flight_num AND t.airline_name = f.airline_name
                WHERE p.booking_agent_id = %s
                    AND p.purchase_date BETWEEN %s AND %s;
            """, (booking_agent_id, start_date, end_date))
            
            data = cursor.fetchone()
            custom_commission = data['total_commission'] if data['total_commission'] else 0
            custom_tickets_sold = data['total_tickets_sold'] if data['total_tickets_sold'] else 0
            custom_avg_commission = data['avg_commission_per_ticket'] if data['avg_commission_per_ticket'] else 0
            custom_avg_commission = round(custom_avg_commission, 2)

        ############################ Top 5 customers
        # Query for top 5 customers by number of tickets bought
        cursor.execute("""
            SELECT p.customer_email, COUNT(p.ticket_id) AS tickets_bought
            FROM purchases p
            JOIN ticket t ON p.ticket_id = t.ticket_id
            WHERE p.purchase_date >= CURDATE() - INTERVAL 6 MONTH
            GROUP BY p.customer_email
            ORDER BY tickets_bought DESC
            LIMIT 5;
        """)
        top_5_customers_by_tickets = cursor.fetchall()

        # Query for top 5 customers by commission
        cursor.execute("""
            SELECT p.customer_email, SUM(f.price * 0.05) AS commission_received
            FROM purchases p
            JOIN ticket t ON p.ticket_id = t.ticket_id
            JOIN flight f ON t.flight_num = f.flight_num
            WHERE p.purchase_date >= CURDATE() - INTERVAL 1 YEAR
            GROUP BY p.customer_email
            ORDER BY commission_received DESC
            LIMIT 5;
        """)
        top_5_customers_by_commission = cursor.fetchall()

    except Exception as e:
        flash(f'Error retrieving commission data: {e}', 'danger')
        return redirect(url_for('home'))
    finally:
        cursor.close()
        conn.close()

    return render_template('booking_agent_dashboard.html', upcoming_flights=upcoming_flights,
                            departure_airports=departure_airports, arrival_airports=arrival_airports,
                            total_commission=total_commission,
                            total_tickets_sold=total_tickets_sold,
                            avg_commission_per_ticket=avg_commission_per_ticket,
                            custom_commission=custom_commission,
                            custom_tickets_sold=custom_tickets_sold,
                            custom_avg_commission=custom_avg_commission,
                            top_5_customers_by_tickets=top_5_customers_by_tickets,
                            top_5_customers_by_commission=top_5_customers_by_commission)

# Booking Agent Search Flights
@login_required
@app.route('/agent_search_flights', methods=['GET', 'POST'])
def agent_search_flights():
    user_email = session['user_email']
    role = session['role']

    # Initialize variables for GET request (to prevent None values)
    source = destination = date = None
    # source = 'JFK'
    # destination = 'PVG'
    # date = '2024-10-10'

    if request.method == 'POST':
        source = request.form.get('source')
        destination = request.form.get('destination')
        date = request.form.get('date')

    # Check if the user is a booking agent
    if role != 'booking_agent':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Get the airline associated with the booking agent
        cursor.execute("SELECT airline_name FROM booking_agent_work_for WHERE email = %s", (user_email,))
        booking_agent = cursor.fetchone()

        if not booking_agent:
            flash('No airline association found for this booking agent.', 'danger')
            return redirect(url_for('home'))

        airline_name = booking_agent['airline_name']

        # Validate input fields only for POST request (not GET)
        if request.method == 'POST' and (not source or not destination or not date):
            flash('All fields are required to search flights.', 'danger')
            return render_template('agent_search_results.html', 
                                   source=source,
                                   destination=destination,
                                   date=date,
                                   search_failed=True)

        # Search flights restricted to the booking agent's airline
        query = """
            SELECT * FROM flight
            WHERE departure_airport = %s 
                AND arrival_airport = %s 
                AND DATE(departure_time) = %s
                AND airline_name = %s
        """
        cursor.execute(query, (source, destination, date, airline_name))
        flights = cursor.fetchall()

    except Exception as e:
        flash(f"An error occurred: {e}", 'danger')
        flights = []  # Ensure flights is always defined

    finally:
        cursor.close()
        conn.close()

    # Render the agent-specific search results
    return render_template('agent_search_results.html', 
                           flights=flights, 
                           search_failed=(len(flights) == 0),
                           source=source,
                           destination=destination,
                           date=date)

# Booking Agent Purchase Ticket
@app.route('/agent_purchase_ticket', methods=['POST'])
@login_required
def agent_purchase_ticket():
    user_email = session['user_email']
    role = session['role']

    if role != 'booking_agent':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('home'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)  # Using dictionary=True for consistent fetches

    try:
        print(f"Agent Purchase Ticket - User Email: {user_email}, Role: {role}")

        # Get the booking agent ID based on the logged-in agent's email
        cursor.execute("SELECT booking_agent_id FROM booking_agent WHERE email = %s", (user_email,))
        booking_agent = cursor.fetchone()
        print(f"Booking Agent ID Query Result: {booking_agent}")

        if not booking_agent:
            flash('Booking agent ID not found. Please contact support.', 'danger')
            return redirect(url_for('agent_search_flights'))

        booking_agent_id = booking_agent['booking_agent_id']
        print(f"Booking Agent ID: {booking_agent_id}")

        # Get the airline associated with the booking agent
        cursor.execute("SELECT airline_name FROM booking_agent_work_for WHERE email = %s", (user_email,))
        agent_airline = cursor.fetchone()
        print(f"Agent Airline Query Result: {agent_airline}")

        if not agent_airline:
            flash('No airline association found for this booking agent.', 'danger')
            return redirect(url_for('agent_search_flights'))

        airline_name = agent_airline['airline_name']
        flight_num = request.form['flight_num']
        customer_email = request.form['customer_email']

        print(f"Flight Number: {flight_num}, Customer Email: {customer_email}, Airline Name: {airline_name}")

        # Find an available ticket for the flight
        query = """
            SELECT t.ticket_id 
            FROM ticket t
            LEFT JOIN purchases p ON t.ticket_id = p.ticket_id
            WHERE t.flight_num = %s AND p.ticket_id IS NULL
            LIMIT 1;
        """
        cursor.execute(query, (flight_num,))
        ticket = cursor.fetchone()
        print(f"Available Ticket Query Result: {ticket}")

        if not ticket:
            flash('No available tickets for this flight.', 'danger')
            return redirect(url_for('agent_search_flights'))

        ticket_id = ticket['ticket_id']
        print(f"Selected Ticket ID: {ticket_id}")

        # Ensure the customer exists
        cursor.execute("SELECT * FROM customer WHERE email = %s", (customer_email,))
        customer = cursor.fetchone()
        print(f"Customer Query Result: {customer}")

        if not customer:
            flash('Customer email not found. Please check the email and try again.', 'danger')
            return redirect(url_for('agent_search_flights'))

        # Insert the purchase record
        print(f"Attempting to Insert: ticket_id={ticket_id}, customer_email={customer_email}, booking_agent_id={booking_agent_id}")
        cursor.execute("""
            INSERT INTO purchases (ticket_id, customer_email, booking_agent_id, purchase_date)
            VALUES (%s, %s, %s, CURDATE());
        """, (ticket_id, customer_email, booking_agent_id))
        conn.commit()
        print("Purchase record inserted successfully.")

        flash('Flight successfully booked for customer!', 'success')
        return redirect(url_for('booking_agent_dashboard'))

    except Exception as e:
        conn.rollback()
        flash(f'Error booking flight: {e}', 'danger')
        print(f"Exception occurred: {e}")
        return redirect(url_for('booking_agent_dashboard'))

    finally:
        cursor.close()
        conn.close()
        print("Database connection closed.")

####################################################################################################

# Airline Staff
@app.route('/airline_staff_dashboard', methods=['GET', 'POST'])
@login_required
def airline_staff_dashboard():
    user_email = session['user_email']
    role = session['role']

    # Only Admins or authorized airline staff can access this route
    if role != 'airline_staff': #or not check_admin_permissions(user_email)
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))

    # Check which staff permissions this user has
    if check_admin_permissions(user_email) and check_operator_permission(user_email):
        flash('You are logged in as an admin and operator.', 'success')
    elif check_admin_permissions(user_email):
        flash('You are logged in as an admin.', 'success')
    elif check_operator_permission(user_email):
        flash('You are logged in as an operator.', 'success')
    else:
        flash('You are logged in as a regular airline staff member.', 'success')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Fetch the airline name for the logged-in airline staff
        cursor.execute("SELECT airline_name FROM airline_staff WHERE username = %s", (user_email,))
        airline_name = cursor.fetchone()['airline_name']

        # Default query to get upcoming flights (next 30 days)
        query = """
            SELECT f.flight_num, f.departure_time, f.arrival_time, f.departure_airport, f.arrival_airport,
                   f.airline_name, COUNT(p.ticket_id) AS num_customers
            FROM flight f
            LEFT JOIN ticket t ON f.flight_num = t.flight_num AND f.airline_name = t.airline_name
            LEFT JOIN purchases p ON t.ticket_id = p.ticket_id
            WHERE f.airline_name = %s AND f.departure_time >= CURDATE()
            GROUP BY f.flight_num
            HAVING f.departure_time <= CURDATE() + INTERVAL 30 DAY
            ORDER BY f.departure_time;
        """
        cursor.execute(query, (airline_name,))
        flights = cursor.fetchall()

        # Custom filtering based on date range, airports/cities
        if request.method == 'POST':
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            source_airport = request.form['source_airport']
            destination_airport = request.form['destination_airport']

            query = """
                SELECT f.flight_num, f.departure_time, f.arrival_time, f.departure_airport, f.arrival_airport,
                       COUNT(p.ticket_id) AS num_customers
                FROM flight f
                LEFT JOIN ticket t ON f.flight_num = t.flight_num AND f.airline_name = t.airline_name
                LEFT JOIN purchases p ON t.ticket_id = p.ticket_id
                WHERE f.airline_name = %s
                AND f.departure_time BETWEEN %s AND %s
                AND f.departure_airport LIKE %s
                AND f.arrival_airport LIKE %s
                GROUP BY f.flight_num
                ORDER BY f.departure_time;
            """
            cursor.execute(query, (airline_name, start_date, end_date, f'%{source_airport}%', f'%{destination_airport}%'))
            flights = cursor.fetchall()

        # Query to get customers for each flight
        flight_customers = {}
        for flight in flights:
            cursor.execute("""
                SELECT c.name, c.email
                FROM purchases p
                JOIN ticket t ON p.ticket_id = t.ticket_id
                JOIN customer c ON p.customer_email = c.email
                WHERE t.flight_num = %s AND t.airline_name = %s;
            """, (flight['flight_num'], airline_name))
            customers = cursor.fetchall()
            flight_customers[flight['flight_num']] = customers

    except Exception as e:
        flash(f'Error retrieving flight data: {e}', 'danger')
        return redirect(url_for('home'))
    finally:
        cursor.close()
        conn.close()

    return render_template('airline_staff_dashboard.html',
                           flights=flights, flight_customers=flight_customers,
                           check_admin_permissions=check_admin_permissions,
                           check_operator_permission=check_operator_permission)

# Staff (Admin) Grant New Permissions
@app.route('/grant_permissions', methods=['GET', 'POST'])
@login_required
def grant_permissions():
    user_email = session['user_email']
    role = session['role']

    # Ensure that only Admins can access this route
    if role != 'airline_staff' or not check_admin_permissions(user_email):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        staff_username = request.form['staff_username']
        new_permission = request.form['new_permission']

        try:
            # Check if the staff username exists
            cursor.execute("SELECT * FROM airline_staff WHERE username = %s", (staff_username,))
            staff = cursor.fetchone()

            if not staff:
                flash('Staff member not found.', 'danger')
                return redirect(url_for('grant_permissions'))

            # Check if the staff member already has the requested permission
            cursor.execute("SELECT * FROM permission WHERE username = %s AND permission_type = %s",
                           (staff_username, new_permission))
            existing_permission = cursor.fetchone()

            if existing_permission:
                flash('This staff member already has this permission.', 'danger')
                return redirect(url_for('grant_permissions'))

            # Insert the new permission for the staff member
            cursor.execute("INSERT INTO permission (username, permission_type) VALUES (%s, %s)",
                           (staff_username, new_permission))
            conn.commit()

            flash('Permission granted successfully!', 'success')
            return redirect(url_for('grant_permissions'))

        except Exception as e:
            conn.rollback()
            flash(f'Error granting permission: {e}', 'danger')
            return redirect(url_for('grant_permissions'))
        finally:
            cursor.close()
            conn.close()

    # Fetch all airline staff members for the form based on the logged-in user's airline
    cursor.execute("SELECT username, first_name, last_name FROM airline_staff WHERE airline_name = %s", 
                   (session['airline_name'],))
    staff_members = cursor.fetchall()

    return render_template('grant_permissions.html', staff_members=staff_members)

# Helper function to check if the logged-in staff has "Admin" permission
def check_admin_permissions(user_email):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM permission WHERE username = %s AND permission_type = 'Admin'", (user_email,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result is not None

# Helper function to check if the logged-in staff has "Operator" permission
def check_operator_permission(user_email):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM permission WHERE username = %s AND permission_type = 'Operator'", (user_email,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result is not None

# Staff (Admin) Add Booking Agent
@app.route('/add_booking_agent', methods=['GET', 'POST'])
@login_required
def add_booking_agent():
    user_email = session['user_email']
    role = session['role']

    # Ensure that only Admins can access this route
    if role != 'airline_staff' or not check_admin_permissions(user_email):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        booking_agent_email = request.form['booking_agent_email']

        try:
            # Check if the email already exists in the booking_agent table
            cursor.execute("SELECT * FROM booking_agent WHERE email = %s", (booking_agent_email,))
            existing_agent = cursor.fetchone()

            if existing_agent:
                flash('This booking agent already exists.', 'danger')
                return redirect(url_for('add_booking_agent'))

            # Generate a hashed password for the booking agent
            default_password = '1234'
            hashed_password = bcrypt.generate_password_hash(default_password).decode('utf-8')

            # Insert the new booking agent into the booking_agent table
            cursor.execute(
                "INSERT INTO booking_agent (email, password, booking_agent_id) VALUES (%s, %s, %s)",
                (booking_agent_email, hashed_password, generate_booking_agent_id())  # Default password and generated ID
            )

            # Get the airline name from the session
            airline_name = session['airline_name']

            # Link the booking agent to the airline in booking_agent_work_for table
            cursor.execute(
                "INSERT INTO booking_agent_work_for (email, airline_name) VALUES (%s, %s)",
                (booking_agent_email, airline_name)
            )
            conn.commit()

            flash('Booking agent added successfully!', 'success')
            return redirect(url_for('add_booking_agent'))

        except Exception as e:
            conn.rollback()
            flash(f'Error adding booking agent: {e}', 'danger')
            return redirect(url_for('add_booking_agent'))
        finally:
            cursor.close()
            conn.close()

    return render_template('add_booking_agent.html')

# Helper function to generate a random booking agent ID
def generate_booking_agent_id():
    # Generate a simple random ID for the booking agent
    return random.randint(1000, 9999)

# Staff (Admin) Add Flight
@app.route('/create_flight', methods=['GET', 'POST'])
@login_required
def create_flight():
    user_email = session['user_email']
    role = session['role']

    # Ensure that only Admins or authorized airline staff can access this route
    if role != 'airline_staff' or not check_admin_permissions(user_email):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        flight_num = request.form['flight_num']
        departure_airport = request.form['departure_airport']
        arrival_airport = request.form['arrival_airport']
        departure_time = request.form['departure_time']
        arrival_time = request.form['arrival_time']
        price = request.form['price']
        status = request.form['status']
        airplane_id = request.form['airplane_id']
        airline_name = session['airline_name']

        try:
            # Ensure flight number is unique for the airline
            cursor.execute("""
                SELECT * FROM flight 
                WHERE airline_name = %s AND flight_num = %s
            """, (airline_name, flight_num))
            existing_flight = cursor.fetchone()

            if existing_flight:
                flash('Flight number already exists for this airline.', 'danger')
                return redirect(url_for('create_flight'))

            # Insert the new flight into the flight table
            cursor.execute("""
                INSERT INTO flight (airline_name, flight_num, departure_airport, departure_time,
                                    arrival_airport, arrival_time, price, status, airplane_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (airline_name, flight_num, departure_airport, departure_time,
                  arrival_airport, arrival_time, price, status, airplane_id))
            conn.commit()

            # Create tickets based on the number of seats on the airplane
            cursor.execute("""
                SELECT seats FROM airplane WHERE airline_name = %s AND airplane_id = %s
            """, (airline_name, airplane_id))
            airplane = cursor.fetchone()
            
            if airplane:
                number_of_seats = airplane['seats']
                for i in range(number_of_seats):
                    cursor.execute("""
                        INSERT INTO ticket (airline_name, flight_num) 
                        VALUES (%s, %s)
                    """, (airline_name, flight_num))
                conn.commit()

            flash('Flight created successfully and tickets added!', 'success')
            return redirect(url_for('airline_staff_dashboard'))  # Redirect to the dashboard

        except Exception as e:
            conn.rollback()
            flash(f'Error creating flight: {e}', 'danger')
            return redirect(url_for('create_flight'))
        finally:
            cursor.close()
            conn.close()

    # Fetch required data for the form (airports, airplane IDs)
    cursor.execute("SELECT airport_name FROM airport")  # Get all airports
    airports = cursor.fetchall()

    cursor.execute("SELECT airplane_id FROM airplane WHERE airline_name = %s", (session['airline_name'],))  # Get airplane IDs
    airplanes = cursor.fetchall()

    return render_template('create_flight.html', airports=airports, airplanes=airplanes)

# Staff (Operator) Change Flight Status
@app.route('/change_flight_status/<airline_name>/<int:flight_num>', methods=['GET', 'POST'])
@login_required
def change_flight_status(airline_name, flight_num):
    user_email = session['user_email']
    role = session['role']

    # Ensure that only airline operator can access this route
    if role != 'airline_staff' or not check_operator_permission(user_email):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        new_status = request.form['status']

        try:
            # Update the status of the flight
            cursor.execute("""
                UPDATE flight 
                SET status = %s
                WHERE airline_name = %s AND flight_num = %s
            """, (new_status, airline_name, flight_num))
            conn.commit()
            flash('Flight status updated successfully!', 'success')
            return redirect(url_for('airline_staff_dashboard'))  # Redirect to the dashboard
        except Exception as e:
            conn.rollback()
            flash(f'Error updating flight status: {e}', 'danger')
            return redirect(url_for('airline_staff_dashboard'))
        finally:
            cursor.close()
            conn.close()

    # Fetch the current flight details for display
    cursor.execute("""
        SELECT flight_num, departure_airport, arrival_airport, departure_time, arrival_time, status
        FROM flight 
        WHERE airline_name = %s AND flight_num = %s
    """, (airline_name, flight_num))
    flight = cursor.fetchone()

    if not flight:
        flash('Flight not found.', 'danger')
        return redirect(url_for('airline_staff_dashboard'))

    return render_template('change_flight_status.html', flight=flight)

# Staff (Admin) Add Airplane
@app.route('/add_airplane', methods=['GET', 'POST'])
@login_required
def add_airplane():
    user_email = session['user_email']
    role = session['role']

    # Ensure that only Admins can access this route
    if role != 'airline_staff' or not check_admin_permissions(user_email):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        airplane_id = request.form['airplane_id']
        seats = request.form['seats']
        airline_name = session['airline_name']  # Get the airline name from session

        try:
            # Ensure airplane ID is unique for the airline
            cursor.execute("""
                SELECT * FROM airplane 
                WHERE airline_name = %s AND airplane_id = %s
            """, (airline_name, airplane_id))
            existing_airplane = cursor.fetchone()

            if existing_airplane:
                flash('Airplane ID already exists for this airline.', 'danger')
                return redirect(url_for('add_airplane'))

            # Insert the new airplane into the airplane table
            cursor.execute("""
                INSERT INTO airplane (airline_name, airplane_id, seats) 
                VALUES (%s, %s, %s)
            """, (airline_name, airplane_id, seats))
            conn.commit()

            flash('Airplane added successfully!', 'success')
            return redirect(url_for('add_airplane'))

        except Exception as e:
            conn.rollback()
            flash(f'Error adding airplane: {e}', 'danger')
            return redirect(url_for('add_airplane'))
        finally:
            cursor.close()
            conn.close()

    return render_template('add_airplane.html')

# Staff (Admin): Airplane List Button
@app.route('/airplane_list')
@login_required
def airplane_list():
    user_email = session['user_email']
    role = session['role']

    # Ensure that only Admins or authorized airline staff can access this route
    if role != 'airline_staff' or not check_admin_permissions(user_email):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Fetch all airplanes for the logged-in airline
        airline_name = session['airline_name']
        cursor.execute("""
            SELECT airplane_id, seats FROM airplane WHERE airline_name = %s
        """, (airline_name,))
        airplanes = cursor.fetchall()

    except Exception as e:
        flash(f'Error retrieving airplanes: {e}', 'danger')
        return redirect(url_for('home'))
    finally:
        cursor.close()
        conn.close()

    return render_template('airplane_list.html', airplanes=airplanes)

# Staff (Admin) Add Airport
@app.route('/add_airport', methods=['GET', 'POST'])
@login_required
def add_airport():
    user_email = session['user_email']
    role = session['role']

    # Ensure that only Admins can access this route
    if role != 'airline_staff' or not check_admin_permissions(user_email):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        airport_name = request.form['airport_name']
        airport_city = request.form['airport_city']

        try:
            # Ensure airport name is unique
            cursor.execute("SELECT * FROM airport WHERE airport_name = %s", (airport_name,))
            existing_airport = cursor.fetchone()

            if existing_airport:
                flash('Airport already exists in the system.', 'danger')
                return redirect(url_for('add_airport'))

            # Insert the new airport into the airport table
            cursor.execute("""
                INSERT INTO airport (airport_name, airport_city) 
                VALUES (%s, %s)
            """, (airport_name, airport_city))
            conn.commit()

            flash('Airport added successfully!', 'success')
            return redirect(url_for('add_airport'))

        except Exception as e:
            conn.rollback()
            flash(f'Error adding airport: {e}', 'danger')
            return redirect(url_for('add_airport'))
        finally:
            cursor.close()
            conn.close()

    return render_template('add_airport.html')

# Staff (Admin): Airport List Button 
@app.route('/airport_list')
@login_required
def airport_list():
    user_email = session['user_email']
    role = session['role']

    # Ensure that only Admins can access this route
    if role != 'airline_staff' or not check_admin_permissions(user_email):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Fetch all airports
        cursor.execute("SELECT airport_name, airport_city FROM airport")
        airports = cursor.fetchall()
    except Exception as e:
        flash(f'Error retrieving airports: {e}', 'danger')
        return redirect(url_for('home'))
    finally:
        cursor.close()
        conn.close()
    return render_template('airport_list.html', airports=airports)

# All Staff: View Top Booking Agents
@app.route('/view_booking_agents')
@login_required
def view_booking_agents():
    user_email = session['user_email']
    role = session['role']

    # Ensure only airline staff can access this route
    if role != 'airline_staff':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Fetch airline name for the logged-in staff member
        cursor.execute("SELECT airline_name FROM airline_staff WHERE username = %s", (user_email,))
        airline_name = cursor.fetchone()['airline_name']

        # Get top 5 booking agents based on the number of tickets sold in the past month
        cursor.execute("""
            SELECT ba.email, COUNT(p.ticket_id) AS tickets_sold
            FROM booking_agent ba
            LEFT JOIN purchases p ON ba.booking_agent_id = p.booking_agent_id
            WHERE p.purchase_date >= CURDATE() - INTERVAL 1 MONTH OR p.purchase_date IS NULL
            GROUP BY ba.email
            ORDER BY tickets_sold DESC
            LIMIT 5
        """)
        top_agents_by_sales_month = cursor.fetchall()

        # Get top 5 booking agents based on the number of tickets sold in the past year
        cursor.execute("""
            SELECT ba.email, COUNT(p.ticket_id) AS tickets_sold
            FROM booking_agent ba
            LEFT JOIN purchases p ON ba.booking_agent_id = p.booking_agent_id
            WHERE p.purchase_date >= CURDATE() - INTERVAL 1 YEAR OR p.purchase_date IS NULL
            GROUP BY ba.email
            ORDER BY tickets_sold DESC
            LIMIT 5
        """)
        top_agents_by_sales_year = cursor.fetchall()

        # Get top 5 booking agents based on the commission earned in the past year
        cursor.execute("""
            SELECT ba.email, COALESCE(SUM(f.price * 0.05), 0) AS commission_received
            FROM booking_agent ba
            LEFT JOIN purchases p ON ba.booking_agent_id = p.booking_agent_id
            LEFT JOIN ticket t ON p.ticket_id = t.ticket_id
            LEFT JOIN flight f ON t.flight_num = f.flight_num AND t.airline_name = f.airline_name
            WHERE p.purchase_date >= CURDATE() - INTERVAL 1 YEAR OR p.purchase_date IS NULL
            GROUP BY ba.email
            ORDER BY commission_received DESC
            LIMIT 5
        """)
        top_agents_by_commission = cursor.fetchall()

    except Exception as e:
        flash(f'Error retrieving booking agents: {e}', 'danger')
        return redirect(url_for('home'))
    finally:
        cursor.close()
        conn.close()

    return render_template('view_booking_agents.html', 
                           top_agents_by_sales_month=top_agents_by_sales_month,
                           top_agents_by_sales_year=top_agents_by_sales_year,
                           top_agents_by_commission=top_agents_by_commission)

# All Staff: View Frequent Customers
@app.route('/view_frequent_customers', methods=['GET', 'POST'])
@login_required
def view_frequent_customers():
    user_email = session['user_email']
    role = session['role']
    
    # Ensure that only Airline Staff can access this route
    if role != 'airline_staff':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get the airline name for the logged-in airline staff
        cursor.execute("SELECT airline_name FROM airline_staff WHERE username = %s", (user_email,))
        airline_name = cursor.fetchone()['airline_name']
        
        # Get the top frequent customers based on ticket purchases in the last year
        cursor.execute("""
            SELECT c.email, c.name, COUNT(p.ticket_id) AS num_tickets
            FROM customer c
            JOIN purchases p ON c.email = p.customer_email
            JOIN ticket t ON p.ticket_id = t.ticket_id
            JOIN flight f ON t.flight_num = f.flight_num AND f.airline_name = %s
            WHERE p.purchase_date >= CURDATE() - INTERVAL 1 YEAR
            GROUP BY c.email
            ORDER BY num_tickets DESC
            LIMIT 5
        """, (airline_name,))
        
        frequent_customers = cursor.fetchall()

        # If a customer is selected, display their flight history
        customer_flights = []
        selected_customer = None
        if request.method == 'POST' and 'customer_email' in request.form:
            selected_customer_email = request.form['customer_email']
            
            # Get the flights for the selected customer
            cursor.execute("""
                SELECT f.flight_num, f.departure_time, f.arrival_time, f.departure_airport, f.arrival_airport
                FROM purchases p
                JOIN ticket t ON p.ticket_id = t.ticket_id
                JOIN flight f ON t.flight_num = f.flight_num AND f.airline_name = %s
                WHERE p.customer_email = %s
            """, (airline_name, selected_customer_email))
            customer_flights = cursor.fetchall()
            selected_customer = next(
                (customer for customer in frequent_customers if customer['email'] == selected_customer_email), 
                None
            )
        
    except Exception as e:
        flash(f"Error retrieving customer data: {e}", 'danger')
        return redirect(url_for('home'))
    finally:
        cursor.close()
        conn.close()

    return render_template('view_frequent_customers.html', 
                           frequent_customers=frequent_customers, 
                           customer_flights=customer_flights,
                           selected_customer=selected_customer)

# All Staff: View Reports
@app.route('/view_reports', methods=['GET', 'POST'])
@login_required
def view_reports():
    user_email = session['user_email']
    role = session['role']
    
    # Ensure only airline staff can access this page
    if role != 'airline_staff':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Initialize variables for the reports
    total_sales = 0
    month_wise_sales = []
    start_date = None
    end_date = None

    try:
        # Get the airline name for the logged-in staff
        cursor.execute("SELECT airline_name FROM airline_staff WHERE username = %s", (user_email,))
        airline_name = cursor.fetchone()['airline_name']
        
        if request.method == 'POST':
            # Handle custom date range
            start_date = request.form['start_date']
            end_date = request.form['end_date']

            # Get total tickets sold within the custom date range
            cursor.execute("""
                SELECT COUNT(p.ticket_id) AS total_sales
                FROM purchases p
                JOIN ticket t ON p.ticket_id = t.ticket_id
                JOIN flight f ON t.flight_num = f.flight_num AND t.airline_name = %s
                WHERE p.purchase_date BETWEEN %s AND %s
            """, (airline_name, start_date, end_date))
            total_sales = cursor.fetchone()['total_sales'] or 0

            # Get month-wise sales for the custom date range
            cursor.execute("""
                SELECT DATE_FORMAT(p.purchase_date, '%Y-%m') AS month, COUNT(p.ticket_id) AS tickets_sold
                FROM purchases p
                JOIN ticket t ON p.ticket_id = t.ticket_id
                JOIN flight f ON t.flight_num = f.flight_num AND t.airline_name = %s
                WHERE p.purchase_date BETWEEN %s AND %s
                GROUP BY month
                ORDER BY month
            """, (airline_name, start_date, end_date))
            month_wise_sales = cursor.fetchall()

        else:
            # Get total tickets sold in the last year
            cursor.execute("""
                SELECT COUNT(p.ticket_id) AS total_sales
                FROM purchases p
                JOIN ticket t ON p.ticket_id = t.ticket_id
                JOIN flight f ON t.flight_num = f.flight_num AND t.airline_name = %s
                WHERE p.purchase_date >= CURDATE() - INTERVAL 1 YEAR
            """, (airline_name,))
            total_sales = cursor.fetchone()['total_sales'] or 0

            # Get month-wise sales for the last year
            cursor.execute("""
                SELECT DATE_FORMAT(p.purchase_date, '%Y-%m') AS month, COUNT(p.ticket_id) AS tickets_sold
                FROM purchases p
                JOIN ticket t ON p.ticket_id = t.ticket_id
                JOIN flight f ON t.flight_num = f.flight_num AND t.airline_name = %s
                WHERE p.purchase_date >= CURDATE() - INTERVAL 1 YEAR
                GROUP BY month
                ORDER BY month
            """, (airline_name,))
            month_wise_sales = cursor.fetchall()

    except Exception as e:
        flash(f'Error retrieving report data: {e}', 'danger')
        return redirect(url_for('home'))
    finally:
        cursor.close()
        conn.close()

    return render_template('view_reports.html', total_sales=total_sales,
                           month_wise_sales=month_wise_sales, start_date=start_date,
                           end_date=end_date)

# All Staff: View Revenue Comparison
@app.route('/view_revenue_comparison', methods=['GET'])
@login_required
def view_revenue_comparison():
    user_email = session['user_email']
    role = session['role']

    # Ensure only airline staff can access this page
    if role != 'airline_staff':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Initialize variables
    direct_revenue_last_month = 0
    indirect_revenue_last_month = 0
    direct_revenue_last_year = 0
    indirect_revenue_last_year = 0

    try:
        # Get the airline name for the logged-in staff
        cursor.execute("SELECT airline_name FROM airline_staff WHERE username = %s", (user_email,))
        airline_name = cursor.fetchone()['airline_name']

        # Revenue for last month (direct sales)
        cursor.execute("""
            SELECT SUM(f.price) AS direct_revenue
            FROM purchases p
            JOIN ticket t ON p.ticket_id = t.ticket_id
            JOIN flight f ON t.flight_num = f.flight_num AND t.airline_name = %s
            WHERE p.booking_agent_id IS NULL AND p.purchase_date >= CURDATE() - INTERVAL 1 MONTH
        """, (airline_name,))
        direct_revenue_last_month = cursor.fetchone()['direct_revenue'] or 0

        # Revenue for last month (indirect sales)
        cursor.execute("""
            SELECT SUM(f.price) AS indirect_revenue
            FROM purchases p
            JOIN ticket t ON p.ticket_id = t.ticket_id
            JOIN flight f ON t.flight_num = f.flight_num AND t.airline_name = %s
            WHERE p.booking_agent_id IS NOT NULL AND p.purchase_date >= CURDATE() - INTERVAL 1 MONTH
        """, (airline_name,))
        indirect_revenue_last_month = cursor.fetchone()['indirect_revenue'] or 0

        # Revenue for last year (direct sales)
        cursor.execute("""
            SELECT SUM(f.price) AS direct_revenue
            FROM purchases p
            JOIN ticket t ON p.ticket_id = t.ticket_id
            JOIN flight f ON t.flight_num = f.flight_num AND t.airline_name = %s
            WHERE p.booking_agent_id IS NULL AND p.purchase_date >= CURDATE() - INTERVAL 1 YEAR
        """, (airline_name,))
        direct_revenue_last_year = cursor.fetchone()['direct_revenue'] or 0

        # Revenue for last year (indirect sales)
        cursor.execute("""
            SELECT SUM(f.price) AS indirect_revenue
            FROM purchases p
            JOIN ticket t ON p.ticket_id = t.ticket_id
            JOIN flight f ON t.flight_num = f.flight_num AND t.airline_name = %s
            WHERE p.booking_agent_id IS NOT NULL AND p.purchase_date >= CURDATE() - INTERVAL 1 YEAR
        """, (airline_name,))
        indirect_revenue_last_year = cursor.fetchone()['indirect_revenue'] or 0

    except Exception as e:
        flash(f'Error retrieving revenue data: {e}', 'danger')
        return redirect(url_for('home'))
    finally:
        cursor.close()
        conn.close()

    return render_template('view_revenue_comparison.html', 
                           direct_revenue_last_month=direct_revenue_last_month,
                           indirect_revenue_last_month=indirect_revenue_last_month,
                           direct_revenue_last_year=direct_revenue_last_year,
                           indirect_revenue_last_year=indirect_revenue_last_year)

# All Staff: View Top Destinations
@app.route('/view_top_destinations', methods=['GET'])
@login_required
def view_top_destinations():
    user_email = session['user_email']
    role = session['role']

    # Ensure that only airline staff can access this page
    if role != 'airline_staff':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    top_destinations_last_3_months = []
    top_destinations_last_year = []

    try:
        # Get the airline name for the logged-in staff
        cursor.execute("SELECT airline_name FROM airline_staff WHERE username = %s", (user_email,))
        airline_name = cursor.fetchone()['airline_name']

        # Top 3 destinations for the last 3 months
        cursor.execute("""
            SELECT f.arrival_airport, a.airport_city, COUNT(f.flight_num) AS num_flights
            FROM flight f
            JOIN airport a ON f.arrival_airport = a.airport_name
            WHERE f.airline_name = %s AND f.departure_time >= CURDATE() - INTERVAL 3 MONTH
            GROUP BY f.arrival_airport
            ORDER BY num_flights DESC
            LIMIT 3
        """, (airline_name,))
        top_destinations_last_3_months = cursor.fetchall()

        # Top 3 destinations for the last year
        cursor.execute("""
            SELECT f.arrival_airport, a.airport_city, COUNT(f.flight_num) AS num_flights
            FROM flight f
            JOIN airport a ON f.arrival_airport = a.airport_name
            WHERE f.airline_name = %s AND f.departure_time >= CURDATE() - INTERVAL 1 YEAR
            GROUP BY f.arrival_airport
            ORDER BY num_flights DESC
            LIMIT 3
        """, (airline_name,))
        top_destinations_last_year = cursor.fetchall()

    except Exception as e:
        flash(f'Error retrieving top destinations data: {e}', 'danger')
        return redirect(url_for('home'))
    finally:
        cursor.close()
        conn.close()

    return render_template('view_top_destinations.html',
                           top_destinations_last_3_months=top_destinations_last_3_months,
                           top_destinations_last_year=top_destinations_last_year)

####################################################################################################

if __name__ == '__main__':
    app.run(debug=True, port=5002)