import os
from os.path import join, dirname, realpath
from flask import *
from flask_cors import CORS
from fileinput import filename
from werkzeug.utils import secure_filename
import mysql.connector
import requests
import json
from PyPDF2 import PdfReader


UPLOAD_FOLDER = join(dirname(realpath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'pdf'}

# Create Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'mysecretkey'
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


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # If the user does not select a file, the browser submits an empty file without a filename
        if file.filename == '':
            flash('No file selected, please select a file.')
            return redirect(request.url)
        # Check if the file is one of the allowed types/extensions
        if not allowed_file(file.filename):
            flash('That file extension is not allowed. Please upload a .pdf file.')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            address = read_pdf(filename)
            incomplete = not all(address.values())
            if incomplete:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                flash('Please fill in all fields in the PDF.')
                return redirect(request.url)
            return json.dumps(address, default=str)

    return render_template("upload.html")


@app.route('/uploads/<name>')
def download_file(name):
    return send_from_directory(app.config["UPLOAD_FOLDER"], name)

# Functions


def read_pdf(filename):
    reader = PdfReader(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    address = reader.get_form_text_fields()
    return address


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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
