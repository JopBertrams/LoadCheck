import os
from flask import Flask, render_template
from flask_cors import CORS
import mysql.connector
import requests
import json

# Create Flask app
app = Flask(__name__)
CORS(app)

# Create MySQL connection
db = mysql.connector.connect(
    host=os.environ['DBHOST'], user=os.environ['DBUSER'], passwd=os.environ['DBPASS'], db=os.environ['DBNAME'], port=os.environ['DBPORT'])
cursor = db.cursor(dictionary=True)
db.autocommit = True


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/students')
def get_students():
    cursor.execute("SELECT * FROM students;")
    students = cursor.fetchall()
    return json.dumps(students, default=str)


@app.route('/students/<id>')
def get_student(id):
    cursor.execute("SELECT * FROM students WHERE id = %s;", (id,))
    student = cursor.fetchone()
    return json.dumps(student, default=str)


@app.route('/students/<id>/loadsheddinggroup')
def get_student_loadshedding_group(id):
    cursor.execute("SELECT * FROM students WHERE id = %s;", (id,))
    student = cursor.fetchone()
    if student['loadsheddingGroup'] == None:
        # TODO: Get loadshedding group from Eskom API and save to database
        return json.dumps(get_loadshedding_group(student), default=str)
    return json.dumps(student['loadsheddingGroup'], default=str)


@app.route('/students/<id>/loadsheddingschedule')
def get_student_loadshedding_schedule(id):
    cursor.execute("SELECT * FROM students WHERE id = %s;", (id,))
    student = cursor.fetchone()
    if student['loadsheddingGroup'] == None:
        return json.dumps('Student has no loadshedding group', default=str)
    # Get loadshedding schedule from Eskom API
    api_url = 'https://developer.sepush.co.za/business/2.0/area?id=' + \
        student['loadsheddingGroup']
    response = requests.get(
        api_url, headers={'token': os.environ['SEPUSHTOKEN']})
    return json.dumps(response.json(), default=str)


@app.route('/classes')
def get_classes():
    cursor.execute("SELECT * FROM classes;")
    classes = cursor.fetchall()
    return json.dumps(classes, default=str)


@app.route('/classes/<id>')
def get_class(id):
    cursor.execute("SELECT * FROM classes WHERE id = %s;", (id,))
    class_ = cursor.fetchone()
    return json.dumps(class_, default=str)


@app.route('/classes/<id>/students')
def get_class_students(id):
    cursor.execute("SELECT students.* FROM students JOIN student_classes ON students.id = student_classes.student_id JOIN classes ON classes.id = student_classes.class_id WHERE classes.id = %s;", (id,))
    students = cursor.fetchall()
    return json.dumps(students, default=str)

# Functions


def get_loadshedding_group(student):
    # Check if student has coordinates
    # If not, get coordinates from Nominatim API
    coordinates = ''
    if student['coordinates_lat'] == None or student['coordinates_lon'] == None:
        coordinates = get_coordinates(student['address'])
        cursor.execute("UPDATE students SET coordinates_lat = %s, coordinates_lon = %s WHERE id = %s;",
                       (coordinates[0], coordinates[1], student['id']))
    else:
        coordinates = student['coordinates_lat'], student['coordinates_lon']
    # Get loadshedding group from Eskom API
    api_url = 'https://developer.sepush.co.za/business/2.0/areas_nearby?lat=' + \
        str(coordinates[0]) + '&lon=' + str(coordinates[1])
    response = requests.get(
        api_url, headers={'token': os.environ['SEPUSHTOKEN']})
    loadshedding_group = response.json()['areas'][0]['id']
    # Save loadshedding group to database
    cursor.execute("UPDATE students SET loadsheddingGroup = %s WHERE id = %s;",
                   (loadshedding_group, student['id']))
    return loadshedding_group


def get_coordinates(address):
    # Get coordinates from Nominatim API
    api_url = 'https://nominatim.openstreetmap.org/search?q=' + address + '&format=json'
    response = requests.get(api_url)
    coordinates = response.json()[0]['lat'], response.json()[0]['lon']
    print(coordinates)
    return coordinates
