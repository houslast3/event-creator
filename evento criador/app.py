from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///eventos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    events_created = db.relationship('Event', backref='creator', lazy=True)
    events_attending = db.relationship('EventAttendee', backref='user', lazy=True)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    image_url = db.Column(db.String(500))
    is_private = db.Column(db.Boolean, default=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    attendees = db.relationship('EventAttendee', backref='event', lazy=True)
    messages = db.relationship('EventMessage', backref='event', lazy=True)

class EventAttendee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, declined

class EventMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_private = db.Column(db.Boolean, default=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    public_events = Event.query.filter_by(is_private=False).all()
    return render_template('index.html', events=public_events)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
            
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/create_event', methods=['GET', 'POST'])
@login_required
def create_event():
    if request.method == 'POST':
        event = Event(
            title=request.form.get('title'),
            description=request.form.get('description'),
            date=datetime.strptime(request.form.get('date'), '%Y-%m-%dT%H:%M'),
            location=request.form.get('location'),
            image_url=request.form.get('image_url'),
            is_private=bool(request.form.get('is_private')),
            creator_id=current_user.id
        )
        db.session.add(event)
        db.session.commit()
        return redirect(url_for('event_detail', event_id=event.id))
    return render_template('create_event.html')

@app.route('/event/<int:event_id>')
def event_detail(event_id):
    event = Event.query.get_or_404(event_id)
    return render_template('event_detail.html', event=event)

@app.route('/my_events')
@login_required
def my_events():
    created_events = Event.query.filter_by(creator_id=current_user.id).all()
    attending_events = [ea.event for ea in current_user.events_attending]
    return render_template('my_events.html', created_events=created_events, attending_events=attending_events)

@app.route('/event/<int:event_id>/attend', methods=['POST'])
@login_required
def attend_event(event_id):
    event = Event.query.get_or_404(event_id)
    if not EventAttendee.query.filter_by(user_id=current_user.id, event_id=event_id).first():
        attendee = EventAttendee(user_id=current_user.id, event_id=event_id, status='confirmed')
        db.session.add(attendee)
        db.session.commit()
    return redirect(url_for('event_detail', event_id=event_id))

# Socket.IO events
@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)

@socketio.on('leave')
def on_leave(data):
    room = data['room']
    leave_room(room)

@socketio.on('message')
def handle_message(data):
    message = EventMessage(
        content=data['message'],
        event_id=data['event_id'],
        user_id=current_user.id,
        is_private=data.get('is_private', False),
        recipient_id=data.get('recipient_id')
    )
    db.session.add(message)
    db.session.commit()
    
    emit('message', {
        'message': message.content,
        'username': current_user.username,
        'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    }, room=data['room'])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True)
