from datetime import datetime, time, timedelta
import os
from flask import *
from flask_cors import CORS
import mysql.connector
import requests
import json

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecretkey'
CORS(app)

# Routes


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/students')
def get_students():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM students;")
    students = cursor.fetchall()
    cursor.close()
    return json.dumps(students, default=str)


@app.route('/students/<id>', methods=['GET', 'PATCH'])
def get_update_student(id):
    if request.method == 'GET':
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students WHERE student_id = %s;", (id,))
        student = cursor.fetchone()
        cursor.close()
        return json.dumps(student, default=str)
    elif request.method == 'PATCH':
        db = get_db()
        cursor = db.cursor(dictionary=True)
        data = request.get_json()
        loadsheddingArea = data['loadshedding_area']
        calendarName = data['calendar_name']
        cursor.execute("UPDATE students SET loadshedding_area = %s, calendar_name = %s WHERE student_id = %s;",
                       (loadsheddingArea, calendarName, id,))
        db.commit()
        cursor.close()
        return "Success", 200


@app.route('/students/<id>/loadsheddingschedule')
def get_student_loadshedding_schedule(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT calendar_name FROM students WHERE student_id = %s;", (id,))
    calendar_name = cursor.fetchone()[0]
    cursor.close()
    if calendar_name == None:
        return json.dumps('Student has not given loadshedding area yet', default=str)
    else:
        calendar_name = calendar_name[:-4]
    api_url = 'https://eskom-calendar-api.shuttleapp.rs/outages/' + calendar_name
    response = requests.get(api_url)
    return response.json()


@app.route('/loadshedding/tshwane_campus')
def get_tshwane_campus_loadshedding_schedule():
    # Get loadshedding schedule from Eskom API
    api_url = 'https://eskom-calendar-api.shuttleapp.rs/outages/gauteng-tshwane-group-10'
    response = requests.get(api_url)
    loadsheddingToday = []
    loadsheddingTomorrow = []
    for event in response.json():
        # Check if the date of event.start is today
        if datetime.strptime(event['start'], '%Y-%m-%dT%H:%M:%S%z').date() == datetime.today().date():
            loadsheddingToday.append(event)
        # Check if the date of event.start is tomorrow
        if datetime.strptime(event['finsh'], '%Y-%m-%dT%H:%M:%S%z').date() == (datetime.today() + timedelta(days=1)).date():
            loadsheddingTomorrow.append(event)
    return json.dumps({'today': loadsheddingToday, 'tomorrow': loadsheddingTomorrow}, default=str)


@app.route('/classinfo/<subject>/<classtime>/<classdate>')
def getClassInfo(subject, classtime, classdate):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    # Get students in class
    api_url = os.environ['GETSTUDENTSAPI'] + subject
    response = requests.get(api_url)
    if response.status_code == 200:
        studentsInClass = response.json()
        studentIds = [student[os.environ['STUDENTID']]
                      for student in studentsInClass]
    else:
        studentsInClass = []
        studentIds = []
    # Get students from DB
    cursor.execute(
        "SELECT * FROM students WHERE student_id IN" +
        str(tuple(studentIds)) + ";")
    students = cursor.fetchall()
    cursor.close()
    # Not all students from this class are in the DB yet
    if len(students) != len(studentsInClass):
        foundIds = [student['student_id'] for student in students]
        missingIds = list(set(studentIds) - set(foundIds))
        add_missing_students_to_db(missingIds, studentsInClass)
    # Getting distinct loadshedding areas by using a set and then converting it back to a list
    distinctLoadsheddingAreas = set([student["calendar_name"]
                                     for student in students if student["calendar_name"] is not None])
    distinctLoadsheddingAreas = list(distinctLoadsheddingAreas)
    # Get loadshedding info for each distinct area
    loadsheddingInfo = {}
    for loadsheddingArea in distinctLoadsheddingAreas:
        loadsheddingArea = loadsheddingArea[:-4]
        api_url = 'https://eskom-calendar-api.shuttleapp.rs/outages/' + \
            loadsheddingArea
        print('HERE:' + api_url)
        response = requests.get(api_url)
        if response.status_code == 200:
            loadsheddingInfo[loadsheddingArea] = response.json()
    classInfo = {
        "subject": subject,
        "amountOfStudents": len(studentsInClass),
        "time": classtime,
    }
    amountOfStudentsWithLoadshedding = 0
    amountOfStudentsWithoutAddress = 0
    classdate = datetime.strptime(classdate, "%Y-%m-%dT%H:%M:%S.%fZ").date()
    for student in students:
        # Check if student has loadshedding
        if student["calendar_name"] is None:
            student["loadshedding_info"] = []
            student["has_given_address"] = False
            amountOfStudentsWithoutAddress += 1
        else:
            student["loadshedding_info"] = loadsheddingInfo[student["calendar_name"][:-4]]
            student["has_given_address"] = True

        if classtime == "AM":
            class_start_time = time(hour=8, minute=0)
            class_end_time = time(hour=12, minute=0)
        elif classtime == 'PM':
            class_start_time = time(hour=13, minute=0)
            class_end_time = time(hour=17, minute=0)

        loadshedding_periods = student["loadshedding_info"]
        loadshedding_occurs = False

        # Check if loadshedding occurs during class
        for period in loadshedding_periods:
            loadshedding_start_time = datetime.fromisoformat(period['start'])
            loadshedding_end_time = datetime.fromisoformat(period['finsh'])

            if loadshedding_start_time.date() <= classdate <= loadshedding_end_time.date():
                if loadshedding_start_time.time() <= class_end_time and loadshedding_end_time.time() >= class_start_time:
                    loadshedding_occurs = True
                    break

        if loadshedding_occurs:
            student["has_loadshedding_during_class"] = True
            amountOfStudentsWithLoadshedding += 1
        else:
            student["has_loadshedding_during_class"] = False

    classInfo["students"] = students
    classInfo["amountOfStudentsWithLoadshedding"] = amountOfStudentsWithLoadshedding
    classInfo["amountOfStudentsWithoutAddress"] = amountOfStudentsWithoutAddress
    classInfo["PercentageOfStudentsWithLoadshedding"] = (
        amountOfStudentsWithLoadshedding / len(studentsInClass)) * 100

    return classInfo


# Functions


def get_db():
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host=os.environ['DBHOST'], user=os.environ['DBUSER'], passwd=os.environ['DBPASS'], db=os.environ['DBNAME'], port=os.environ['DBPORT'])
        g.db.autocommit = True
    return g.db


@ app.teardown_appcontext
def close_db(error):
    if 'db' in g:
        g.db.close()


def add_missing_students_to_db(missingIds, studentsInClass):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    for studentId in missingIds:
        student = [
            student for student in studentsInClass if student[os.environ['STUDENTID']] == studentId][0]
        cursor.execute("INSERT INTO students (student_id, name, surname) VALUES (%s, %s, %s);",
                       (student[os.environ['STUDENTID']], student['Name'], student['Surname']))
    cursor.close()
    return
