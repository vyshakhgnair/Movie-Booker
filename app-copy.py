from email.mime.application import MIMEApplication
from flask import Flask, request, jsonify,session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from celery import Celery
from datetime import datetime, timedelta
import redis
from sqlalchemy import or_
import pandas as pd
from os.path import basename





app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:5173"}})
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///movie.db'
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Replace with your own secret key
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # Session lifetime

db = SQLAlchemy(app)
jwt = JWTManager(app)


# Initialize Redis connection
redis_db = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)



class user(db.Model):
    userid = db.Column(db.Integer, primary_key=True, unique=True, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    useremail = db.Column(db.String(120), unique=True, nullable=False)
    userpassword = db.Column(db.String(128), nullable=False)
    admin = db.Column(db.Boolean, default=False)


    def __repr__(self):
        return f"<User {self.username}>"

class venue(db.Model):
    venueid = db.Column(db.Integer, primary_key=True, unique=True, nullable=False)
    venuename = db.Column(db.String(100), nullable=False)
    venueplace = db.Column(db.String(100), nullable=False)
    venuelocation = db.Column(db.String(100), nullable=False)
    venuecapacity = db.Column(db.Integer, nullable=False)

    venueshows = db.relationship('venueshow', backref='venue', lazy=True)

class show(db.Model):
    showid = db.Column(db.Integer, primary_key=True, unique=True, nullable=False)
    showname = db.Column(db.String(100), nullable=False)
    showrating = db.Column(db.Integer, nullable=False)
    showtags = db.Column(db.String(100), nullable=False)


class venueshow(db.Model):
    venueshowid = db.Column(db.Integer, primary_key=True, unique=True, nullable=False)
    venueid = db.Column(db.Integer, db.ForeignKey('venue.venueid'), nullable=False)
    showid = db.Column(db.Integer, db.ForeignKey('show.showid'), nullable=False)
    showdate = db.Column(db.String(100), nullable=False)
    timing = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    bookedseats= db.Column(db.Integer, default=0)

    # Define the relationship with the 'show' model
    show = db.relationship('show', backref='venueshows', lazy=True) 

class booking(db.Model):
    bookingid = db.Column(db.Integer, primary_key=True, unique=True, nullable=False)
    showid = db.Column(db.Integer, db.ForeignKey('show.showid'), nullable=False)
    venueid = db.Column(db.Integer, db.ForeignKey('venue.venueid'), nullable=False)
    userid = db.Column(db.Integer, db.ForeignKey('user.userid'), nullable=False)
    seats = db.Column(db.Integer, nullable=False)


class statushistory(db.Model):
    #userid,lastlogin,status(online or offline),primary key is userid
    userid=db.Column(db.Integer,primary_key=True,unique=True,nullable=False)
    lastlogin=db.Column(db.DateTime,nullable=False)
    status=db.Column(db.Integer,default=0)
    


@app.route('/api/register', methods=['POST'])
def register():
    data = request.json

    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Please provide both email and password."}), 400

    existing_user = user.query.filter_by(useremail=email).first()

    if existing_user:
        return jsonify({"error": "Email already registered. Please use a different email."}), 400

    hashed_password = generate_password_hash(password)
    new_user = user(username=username, useremail=email, userpassword=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    #take the userid as output and give email as input
    adduser=user.query.filter_by(useremail=email).first()
    print(adduser.userid)
    activeuser=statushistory(userid=adduser.userid,lastlogin=datetime.now(),status=0)
    print(new_user)
    db.session.add(activeuser)
    db.session.commit()

    # Create and return the access token for the new user
    access_token = create_access_token(identity=new_user.userid)
    return jsonify({"message": "Registration successful!", "access_token": access_token}), 201



@app.route('/api/login', methods=['POST'])
def login():
    data = request.json

    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({"error": "Please provide both email and password."}), 400

    user_check = user.query.filter_by(useremail=email).first()
    existing_status_record = db.session.query(statushistory).filter(statushistory.userid == user_check.userid).first()
    existing_status_record.status = 1
    existing_status_record.lastlogin = datetime.now()
    db.session.commit()
    if not user or not check_password_hash(user_check.userpassword, password):
        return jsonify({"error": "Invalid credentials."}), 401

    # Authentication successful, create and return the access token

    access_token = create_access_token(identity=user_check.userid)
     # Store access code in Redis
    redis_db.set(user_check.userid, access_token)
    # Start a session for the user
    session.permanent = True
    session['user_id'] = user_check.userid

    return jsonify({"access_token": access_token,
                    "userid":user_check.userid}), 200





@app.route('/api/login-admin', methods=['POST'])
def login_admin():
    data = request.json
    print(data)
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Please provide both email and password."}), 400

    user_check = user.query.filter_by(useremail=email).first()

    if not user_check or not check_password_hash(user_check.userpassword,password) :
        return jsonify({"error": "Invalid credentials."}), 401

    if not user_check.admin:
        return jsonify({"error": "You are not authorized to access this page."}), 403

    # Authentication successful, create and return the access token
    access_token = create_access_token(identity=user_check.userid)
    redis_db.set(user_check.userid, access_token)
    # Start a session for the user
    session.permanent = True
    session['user_id'] = user_check.userid
    return jsonify({"access_token": access_token,
                    "userid":user_check.userid}), 200


@app.route('/api/logout', methods=['POST'])
def logout():
    if 'user_id' in session:
        user_id = session['user_id']

        # Remove access code from Redis
        redis_db.delete(user_id)

        # Clear the session
        session.pop('user_id', None)

        return jsonify({'message': 'Logged out successfully'})
    else:
        return jsonify({'message': 'User is not logged in'})










@app.route('/api/reset', methods=['POST'])
def reset():
    data = request.json
    print(data)
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Please provide both email and password."}), 400

    user_check = user.query.filter_by(useremail=email).first()

    if not user_check:
        return jsonify({"error": "Invalid credentials."}), 401

    hashed_password = generate_password_hash(password)
    user_check.userpassword = hashed_password
    db.session.commit()

    # Authentication successful, create and return the access token
    access_token = create_access_token(identity=user_check.userid)
    return jsonify({"access_token": access_token}), 200



@app.route('/api/create-venue', methods=['POST'])
def create_venue():
    data = request.json
    name = data.get('name')
    place = data.get('place')
    location = data.get('location')
    capacity = data.get('capacity')
    print(data)
    if not name or not place or not location or not capacity:
        return jsonify({"error": "Please provide all the required information."}), 400

    new_venue = venue(venuename=name, venueplace=place, venuelocation=location, venuecapacity=capacity)
    db.session.add(new_venue)
    db.session.commit()


    return jsonify({"message": "Venue created successfully!"}), 201


@app.route('/api/create-show', methods=['POST'])
def create_show():
    data = request.json
    name = data.get('name')
    rating = data.get('rating')
    timing = data.get('timing')
    tags= data.get('tags')

    if not name or not rating:
        return jsonify({"error": "Please provide both name and rating."}), 400

    new_show = show(showname=name, showrating=rating, showtags=tags)
    db.session.add(new_show)
    db.session.commit()

    return jsonify({"message": "Show created successfully!"}), 201




@app.route('/api/create-venueshow', methods=['POST'])
def create_venueshow():
    data = request.json
    venue_id = data.get('venueid')
    show_id = data.get('showid')
    date_str = data.get('ldate')  # Update the key to 'ldate'
    timings = data.get('timing')
    price = data.get('price')
    print(data)

    if not venue_id or not show_id or not date_str or not timings or not price:
        return jsonify({"error": "Please provide all the required information."}), 400



    new_venueshow = venueshow(venueid=venue_id, showid=show_id, showdate=date_str, timing=timings, price=price)

    try:
        db.session.add(new_venueshow)
        db.session.commit()
    except Exception as e:
        print(e)
        db.session.rollback()
        return jsonify({"error": "Failed to create the show. Please try again later."}), 500

    return jsonify({"message": "Show created successfully!"}), 201


@app.route('/api/shows', methods=['GET'])
def get_shows():
    shows = show.query.all()
    show_list = []
    for movie in shows:
        show_data = {
            'showid': movie.showid,
            'showname': movie.showname,
            'showrating': movie.showrating,
            'showtags': movie.showtags
        }
        show_list.append(show_data)
    return jsonify(show_list)




@app.route('/api/venues-with-shows', methods=['GET'])
def get_venues_with_shows():
    try:
        # Fetch venue details along with shows using appropriate database queries
        venues_with_shows = []
        venues = venue.query.all()

        for theatre in venues:
            venue_data = {
                'id': theatre.venueid,
                'name': theatre.venuename,
                'shows': []
            }

            for venue_show in theatre.venueshows:  # Accessing the correct back-reference name
                show_data = {
                    'id': venue_show.showid,
                    'movieName': venue_show.show.showname,  # Access the 'showname' through the relationship
                    'date': venue_show.showdate,
                    'location': theatre.venuelocation
                }
                venue_data['shows'].append(show_data)

            venues_with_shows.append(venue_data)

        return jsonify(venues_with_shows), 200

    except Exception as e:
        print(e)
        return jsonify({"error": "Failed to fetch venues with shows."}), 500





@app.route('/api/delete-show/<int:venue_id>/<int:show_id>', methods=['DELETE'])
def delete_show(venue_id, show_id):
    try:

        screen = venueshow.query.filter_by(showid=show_id, venueid=venue_id).first()

        if screen:
            db.session.delete(screen)
            db.session.commit()
            return jsonify({'message': f'Show with ID {show_id} deleted from venue with ID {venue_id}'}), 200
        else:
            return jsonify({'error': 'Show not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500






@app.route('/api/delete-venue/<int:venue_id>', methods=['DELETE'])
def delete_venue(venue_id):
    try:
        print(venue_id)
        venues = venueshow.query.filter_by(venueid=venue_id).all()

        if venues:
            # Delete each venueshow record associated with the venue_id
            for venue_show in venues:
                db.session.delete(venue_show)
                db.session.commit()
            return jsonify({'message': f'Venue shows with ID {venue_id} deleted successfully'}), 200

        # Delete the main venue record
        mainvenue = venue.query.get(venue_id)
        if mainvenue:
            db.session.delete(mainvenue)
            db.session.commit()
            return jsonify({'message': f'Main Venue with ID {venue_id} deleted successfully'}), 200
        else:
            return jsonify({'error': 'Main Venue not found'}), 404
        
    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 500




@app.route('/api/show/<int:show_id>', methods=['GET'])
def get_show_details(show_id):
    try:
        Show = show.query.get(show_id)
        if not Show:
            return jsonify({"error": "Show not found"}), 404

        show_data = {
            "id": Show.showid,
            "name": Show.showname,
            "rating": Show.showrating,
            "tags": Show.showtags
        }
        print(show_data)
        return jsonify(show_data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/api/update-show/<int:show_id>', methods=['PUT'])
def update_show(show_id):
    try:
        Show = show.query.get(show_id)
        if not Show:
            return jsonify({"error": "Show not found"}), 404

        data = request.json
        Show.showname = data.get('name', Show.showname)
        Show.showrating = data.get('rating', Show.showrating)
        Show.showtags = data.get('tags', Show.showtags)

        db.session.commit()
        return jsonify({"message": "Show updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/api/venue/<int:venue_id>', methods=['GET'])
def get_venue_details(venue_id):
    try:
        venue_record = venue.query.get(venue_id)
        if not venue_record:
            return jsonify({"error": "Venue not found"}), 404

        venue_data = {
            "id": venue_record.venueid,
            "venuename": venue_record.venuename,
            "venueplace": venue_record.venueplace,
            "venuelocation": venue_record.venuelocation,
            "venuecapacity": venue_record.venuecapacity
        }
        print(venue_data)
        return jsonify(venue_data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500





@app.route('/api/edit-venue/<int:venue_id>', methods=['PUT'])
def edit_venue(venue_id):
    try:
        venue_record = venue.query.get(venue_id)
        if not venue_record:
            return jsonify({"error": "Venue not found"}), 404

        data = request.get_json()
        venue_record.venuename = data.get('name', venue_record.venuename)
        venue_record.venueplace = data.get('place', venue_record.venueplace)
        venue_record.venuelocation = data.get('location', venue_record.venuelocation)
        venue_record.venuecapacity = data.get('capacity', venue_record.venuecapacity)

        db.session.commit()

        return jsonify({'message': f'Venue with ID {venue_id} updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500





@app.route('/api/booking-analytics', methods=['GET'])
def get_booking_analytics():
    # Query to count the number of venueshows for each show (movie)
    show_theater_counts = db.session.query(venueshow.showid, db.func.count(venueshow.venueshowid)).\
        group_by(venueshow.showid).all()

    # Convert the result into a dictionary
    movie_theaters = {show_id: count for show_id, count in show_theater_counts}

    # Query all movies from the 'show' table
    movies = show.query.all()

    # Prepare the response data
    movie_data = [{"name": movie.showname, "theaters": movie_theaters.get(movie.showid, 0)} for movie in movies]
    booking_analytics_data = {"movies": movie_data}

    return jsonify(booking_analytics_data)




@app.route('/api/genres', methods=['GET'])
def get_genres():
    genres_query = db.session.query(show.showtags.distinct()).all()
    genres = [{"id": i + 1, "name": genre[0]} for i, genre in enumerate(genres_query)]
    return jsonify(genres)


@app.route('/api/cities', methods=['GET'])
def get_locations():
    locations_query = db.session.query(venue.venueplace.distinct()).all()
    locations = [{"id": i + 1, "name": location[0]} for i, location in enumerate(locations_query)]
    return jsonify(locations)

  


@app.route('/api/search', methods=['POST'])
def search_tickets():
    data = request.get_json()  # Get the JSON data from the request
    genre = data.get('genre')
    city = data.get('city')
    date = data.get('date')

    # Build the query to fetch the shows based on the search criteria
    direct_match_query = db.session.query(venueshow).join(show).join(venue).filter(
        show.showtags == genre, venue.venueplace == city, venueshow.showdate == date).all()

    # If no direct match, try searching individually
    if not direct_match_query:
        date_match_query = db.session.query(venueshow).join(show).join(venue).filter(
            venueshow.showdate == date).all()

        genre_match_query = db.session.query(venueshow).join(show).join(venue).filter(
            show.showtags == genre).all()

        location_match_query = db.session.query(venueshow).join(show).join(venue).filter(
            venue.venueplace == city).all()

        search_query = date_match_query + genre_match_query + location_match_query
    else:
        search_query = direct_match_query

    if not search_query and not direct_match_query:
        search_query=db.session.query(venueshow).join(show).join(venue).all()
    # Convert search results to a list of dictionaries
    search_results = []
    for result in search_query:
        search_results.append({
            "venueid": result.venueid,
            "showid": result.showid,
            "venuename": result.venue.venuename,
            "showname": result.show.showname,
            "venuelocation": result.venue.venuelocation,
            "showdate": result.showdate,
            "timing": result.timing,
            "price": result.price,
            "seats": result.venue.venuecapacity,
            "bookedseats": result.bookedseats,
        })

    print(search_results)
    return jsonify(search_results), 200





@app.route('/api/shows/<int:venueid>/<int:showid>', methods=['GET'])
def get_show_info(venueid, showid):
    print(venueid, showid)
    try:
        showd = venueshow.query.filter_by(venueid=venueid, showid=showid).first()
        print(showd)
        
        if showd:
            show_data = {
                'showid': showd.showid,
                'venueid': showd.venueid,
                'seatprice': showd.price,
                'bookedseats': showd.bookedseats,
 
            }
            print(show_data)
            return jsonify(show_data)
        else:
            return jsonify({'message': 'Show not found'}), 404
    except Exception as e:
        return jsonify({'message': 'An error occurred', 'error': str(e)}), 500





@app.route('/api/bookings', methods=['POST'])
def add_booking():
    try:
        data = request.json        
        print(data)
        new_booking = booking(
            userid=data['userid'],
            showid=data['showid'],
            venueid=data['venueid'],
            seats=data['seatsbooked']
        )
        db.session.add(new_booking)

        # Update bookedseats in venueshow record
        show_to_update = venueshow.query.filter_by(venueid=data['venueid'], showid=data['showid']).first()
        show_to_update.bookedseats += data['seatsbooked']

        db.session.commit()
        return jsonify({'message': 'Booking added successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'An error occurred', 'error': str(e)}), 500


@app.route('/api/bookings/<int:user_id>', methods=['GET'])
def get_user_bookings(user_id):
    try:
        #print(user_id)
        user_bookings = booking.query.filter_by(userid=user_id).all()
        #print(user_bookings)
        bookings_data = []
        for user_booking in user_bookings:
            show_info = show.query.get(user_booking.showid)
            #print(show_info)
            venue_info = venue.query.get(user_booking.venueid)
            #print(venue_info)
            booking_data = {
                'bookingId': user_booking.bookingid,
                'showName': show_info.showname,
                'venueName': venue_info.venuename,
                'venueLocation': venue_info.venuelocation,
                'seatsBooked': user_booking.seats
            }
            bookings_data.append(booking_data)
        #print(booking_data)
        return jsonify(bookings_data)
    except Exception as e:
        return jsonify({'message': 'An error occurred', 'error': str(e)}), 500



@app.route('/api/<int:booking_id>/<int:rating>', methods=['POST'])
def add_rating(booking_id,rating):
    print(booking_id)
    print(rating)
    try:
        booking_record = booking.query.get(booking_id)
        print(booking_record)
        booking_record.rating = rating

        # Update the rating of the show
        show_record = show.query.get(booking_record.showid)
        show_record.showrating = (show_record.showrating + rating) / 2

        db.session.commit()
        return jsonify({'message': 'Rating added successfully'})
    except Exception as e:
        return jsonify({'message': 'An error occurred', 'error': str(e)}), 500




@app.route('/api/cancel/<int:booking_id>', methods=['DELETE'])
def cancel_booking(booking_id): 
    print(booking_id)
    bookings = booking.query.get(booking_id)
    if bookings:
        # Get the corresponding show record     
        vid=bookings.venueid
        sid=bookings.showid

        # Update seat availability for the canceled booking
        ven=venueshow.query.filter_by(venueid=vid, showid=sid).first()
        ven.bookedseats-=bookings.seats

        db.session.delete(bookings)
        db.session.commit()
        return jsonify({'message': 'Booking cancelled successfully'})
    else:
        return jsonify({'message': 'Booking not found'}), 404



@app.route('/api/download/<int:user_id>',methods=['GET'])
def downloadreport(user_id):
    monthly_job.delay(user_id)
    return jsonify({'message':'Mail send'})




# An example of a protected route that requires authentication
@app.route('/api/protected', methods=['GET'])
@jwt_required()
def protected_route():
    current_user_id = get_jwt_identity()
    current_user = user.query.get(current_user_id)
    return jsonify({"message": f"Hello {current_user.username}, you are authenticated!"}), 200


app.config['celery_broker'] = 'redis://localhost:6379/0'  
app.config['backend'] = 'redis://localhost:6379/1'  
celeryapp = Celery(app.name, broker=app.config['celery_broker'])
celeryapp.conf.update(app.config)


celeryapp.conf.beat_schedule = {
    'daily-job':{
        'task': 'app.daily_job',
        'schedule': 86400,  # Run every 24hr 86400
    },

    'monthly-job': {
        'task': 'app.monthly_job',
        'schedule': 2592000,  # Run every 30 days 2592000 (in seconds)
    },
    'monthly-job2': {
        'task': 'app.admin_monthly_job',
        'schedule': 2592000,  # Run every 30 days 2592000 (in seconds)
    },
}

celeryapp.conf.timezone = 'UTC'



@celeryapp.task
def daily_job():
    with app.app_context():
        twenty_four_hours_ago = datetime.now() - timedelta(hours=24)    
        users_to_notify = db.session.query(statushistory).filter(statushistory.lastlogin <= twenty_four_hours_ago).all()
        for user in users_to_notify:
            send_email(user.userid) 
            print("Send to user successfully")
        return len(users_to_notify)



@celeryapp.task
def monthly_job(user_id):
    with app.app_context():
        # Retrieve user information from the database
        users = user.query.get(user_id)

        if users:
            user_bookings = get_bookings(users.userid)
            # Generate the report content
            report = generate_report(user_bookings)

            # Send email to user
            send_report_email(users.useremail, report)
            print(f"Report email sent to user: {users.useremail}")
        else:
            print(f"User with ID {user_id} not found")

    



def send_email(userid):
    # Email configuration
    inactiveuser=db.session.query(user).filter_by(userid=userid).first()
    print(inactiveuser)
    smtp_server = "smtp.gmail.com"  
    smtp_port = 25   
    smtp_username = "vyshakhgnair.cvr@gmail.com"
    smtp_password = "nesaigghheyaemau"
    sender_email = "vyshakhgnair.cvr@gmail.com"
    recipient_email = inactiveuser.useremail 

    # Create the email content
    subject = "Daily Update"
    body = f"Hello {inactiveuser.username},\n\nWe hope this message finds you well. 🎬\n\nWe noticed that you recently explored our movie booking website but haven't finalized your movie plans yet. Don't miss out on the excitement and entertainment that await you!\n\n🍿 Catch the latest blockbusters on the big screen.\n\n🎉 Enjoy a memorable movie night with your loved ones.\n\n🎫 Reserve your seats hassle-free from the comfort of your home.\n\nYour movie experience is just a few clicks away. Head back to our website and grab the best seats for your preferred showtime. Whether you're into action-packed adventures, heartwarming dramas, or side-splitting comedies, we have something special in store for you."
    
    # Create the email message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    # Connect to the SMTP server and send the email
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()
        print("Email sent successfully")
    except Exception as e:
        print("Error sending email:", e)

def get_bookings(user_id):
    try:
        user_bookings = booking.query.filter_by(userid=user_id).all()
        bookings_data = []
        for user_booking in user_bookings:
            show_info = show.query.get(user_booking.showid)
            venue_info = venue.query.get(user_booking.venueid)
            booking_data = {
                'bookingId': user_booking.bookingid,
                'showName': show_info.showname,
                'venueName': venue_info.venuename,
                'venueLocation': venue_info.venuelocation,
                'seatsBooked': user_booking.seats
            }
            bookings_data.append(booking_data)
        return bookings_data
    except Exception as e:
        print(e)  # Print the error for debugging purposes
        return []





def generate_report(bookings_data):
    report = "Here is your monthly movie booking report:\n\n"
    for booking_data in bookings_data:
        report += f"Booking ID: {booking_data['bookingId']}\n"
        report += f"Movie Name: {booking_data['showName']}\n"
        report += f"Venue: {booking_data['venueName']} ({booking_data['venueLocation']})\n"
        report += f"Seats Booked: {booking_data['seatsBooked']}\n\n"

    report += "Don't miss out on more exciting movies this month!\n\nBest regards,\nThe Movie Booking Team"
    return report



def send_report_email(useremail, report):
    # Email configuration
    smtp_server = "smtp.gmail.com"  
    smtp_port = 25   
    smtp_username = "vyshakhgnair.cvr@gmail.com"
    smtp_password = "nesaigghheyaemau"
    sender_email = "vyshakhgnair.cvr@gmail.com"
    recipient_email = useremail

    # Create the email content
    subject = "Monthly Movie Booking Report"
    
    # Create the email message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(report, 'plain'))

    # Connect to the SMTP server and send the email
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()
        print("Report email sent successfully")
    except Exception as e:
        print("Error sending report email:", e)
    

@app.route('/api/admin-monthly/<int:venueid>/<int:userid>',methods=['GET'])
def admin_csv(venueid,userid):
    admin_monthly_job.delay(venueid,userid)
    return jsonify({'message':'Mail send'})

@celeryapp.task
def admin_monthly_job(venueid,userid):
    with app.app_context():
        # Retrieve information on each shows running in the venue and create a csv file for each venue
        venue_shows = venueshow.query.filter_by(venueid=venueid).all()
        print(venue_shows)
        venue_ven = venue.query.get(venueid)
        print(venue_ven)
        venue_name = venue_ven.venuename
        print(venue_name)
        venue_location = venue_ven.venuelocation
        print(venue_location)
        venue_shows_data = []
        for venue_show in venue_shows:
            show_info = show.query.get(venue_show.showid)
            print(show_info)
            venue_shows_data.append({
                'showName': show_info.showname,
                'showDate': venue_show.showdate,
                'showTime': venue_show.timing,
                'seatsBooked': venue_show.bookedseats
            })
        print(venue_shows_data)
        # Create a Pandas DataFrame from the list of dictionaries
        df = pd.DataFrame(venue_shows_data)
        print(df)
        # Create a CSV file from the DataFrame
        csv_file_name = f"{venue_name}_{venue_location}.csv"
        df.to_csv(csv_file_name, index=False)
        print(csv_file_name)
        # Send the CSV file as an email attachment to the current login users mail
        users=user.query.get(userid)
        send_csv_email(users.useremail,csv_file_name, venue_name, venue_location)
        print("CSV email sent successfully")
        
        return jsonify({'message': 'CSV email sent successfully'}), 200




def send_csv_email(usermail,csv_file_name, venue_name, venue_location):
    # Email configuration
    smtp_server = "smtp.gmail.com"  
    smtp_port = 25   
    smtp_username = "vyshakhgnair.cvr@gmail.com"
    smtp_password = "nesaigghheyaemau"
    sender_email = "vyshakhgnair.cvr@gmail.com"
    recipient_email = usermail

    # Create the email content
    subject = f"Monthly Movie Booking Report for {venue_name} ({venue_location})"

    # Create the email message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject

    # Attach the CSV file
    with open(csv_file_name, 'rb') as f:
        part = MIMEApplication(f.read(), Name=basename(csv_file_name))
        part['Content-Disposition'] = f'attachment; filename="{basename(csv_file_name)}"'
        msg.attach(part)

    # Connect to the SMTP server and send the email
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()
        print("CSV email sent successfully")
    except Exception as e:
        print("Error sending CSV email:", e)





if __name__ == '__main__':
    app.run(debug=True) 
    celeryapp.start()





