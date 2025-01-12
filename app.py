import json
import os
from flask import Flask, render_template, request, redirect, url_for, flash
import logging
from logging.handlers import RotatingFileHandler
from opentelemetry import trace
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor

# Flask App Initialization
app = Flask(__name__)
app.secret_key = 'secret'
COURSE_FILE = 'course_catalog.json'
# Set up OpenTelemetry tracing
trace.set_tracer_provider(TracerProvider())
jaeger_exporter = JaegerExporter(
    agent_host_name='localhost',  # Your Jaeger agent's host
    agent_port=6831,  # The port your Jaeger agent is listening on
)
span_processor = BatchSpanProcessor(jaeger_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Instrument Flask with OpenTelemetry
FlaskInstrumentor().instrument_app(app)

# Utility Functions
def load_courses():
    """Load courses from the JSON file."""
    if not os.path.exists(COURSE_FILE):
        return []  # Return an empty list if the file doesn't exist
    with open(COURSE_FILE, 'r') as file:
        return json.load(file)


def save_courses(data):
    """Save new course data to the JSON file."""
    courses = load_courses()  # Load existing courses
    courses.append(data)  # Append the new course
    with open(COURSE_FILE, 'w') as file:
        json.dump(courses, file, indent=4)



# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/catalog')
def course_catalog():
    courses = load_courses()
    return render_template('course_catalog.html', courses=courses)


@app.route('/course/<code>')
def course_details(code):
    courses = load_courses()
    course = next((course for course in courses if course['code'] == code), None)
    if not course:
        flash(f"No course found with code '{code}'.", "error")
        return redirect(url_for('course_catalog'))
    return render_template('course_details.html', course=course)

@app.route('/add_courses')
def add_courses():
    return render_template('add_courses.html')

@app.route('/add_course', methods=['GET', 'POST'])
def add_course():
    if request.method == 'POST':
        name = request.form.get('name')
        semester = request.form.get('semester')
        schedule = request.form.get('schedule')
        code = request.form.get('code')
        instructor = request.form.get('instructor')
        grade = request.form.get('grade')
        des = request.form.get('des')
        class_ = request.form.get('class')

        # Validate inputs
        if not name or not instructor or not semester or not schedule or not code or not grade or not class_:
            flash('All fields are required!', 'error')
            app.logger.error('Course creation failed. Missing fields.')
        else:
            # Add the course to the list (or database)
            new_course = {
                    "code": code,
                    "name": name,
                    "instructor": instructor,
                    "semester": semester,
                    "schedule": schedule,
                    "classroom": class_,
                    "prerequisites": "Basic Python, Linux",
                    "grading": grade,
                    "description": des
                    }
            save_courses(new_course)
            flash('Course added successfully!', 'success')
            app.logger.info(f'New course added: {name}, Instructor: {instructor}, Semester: {semester}') ## Logging need to be implemented
            return redirect(url_for('course_catalog'))

    return render_template('course_catalog.html')

if __name__ == '__main__':
    app.run(debug=True)
