import json
import os
from flask import Flask, render_template, request, redirect, url_for, flash
import logging
from logging.handlers import RotatingFileHandler
from opentelemetry import metrics,trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.metrics import MeterProvider
import time

#Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask App Initialization
app = Flask(__name__)
app.secret_key = 'secret key'
COURSE_FILE = 'course_catalog.json'

# Set up OpenTelemetry tracing
trace.set_tracer_provider(TracerProvider(resource=Resource.create({SERVICE_NAME: "course_portal_service"})))
tracer = trace.get_tracer(__name__)

#Jaeger Exporter setup
jaeger_exporter = JaegerExporter(
    agent_host_name='localhost',  # Your Jaeger agent's host
    agent_port=6831,  # The port your Jaeger agent is listening on
)
span_processor = BatchSpanProcessor(jaeger_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Instrument Flask with OpenTelemetry
FlaskInstrumentor().instrument_app(app)

# Set up OpenTelemetry Metrics
metrics.set_meter_provider(MeterProvider(resource=Resource.create({SERVICE_NAME: "course_portal"})))
meter = metrics.get_meter(__name__)

# Metrics
error_counter = meter.create_counter(name="exceptions", description="number of exceptions caught")
request_counter = meter.create_counter(name="requests", description="number of requests")
# operation_duration = meter.create_counter(name="Duration", description="Operation duration")
operation_duration = meter.create_histogram(
    name="operation_duration",
    unit="ms",
    description="The duration of operations in milliseconds"
)
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
    start_time = time.time()
    courses = load_courses()

    # OpenTelemetry Tracing for Course Catalog
    with tracer.start_as_current_span("view_catalog") as span:
        span.set_attribute("view_catalog.count", len(courses))
        span.set_attribute("http.method", request.method)  # HTTP method attribute
        span.set_attribute("user.ip", request.remote_addr)  # Capture user IP address
        span.add_event("Rendering Course Catalog")

        # Track request counter and processing time
        request_counter.add(1, {"route": "/catalog"})
        operation_duration.record((time.time() - start_time) * 1000, {"route": "/catalog"})
        span.set_attribute("request_counter", request_counter)
        span.set_attribute("operation_duration", operation_duration)
    return render_template('course_catalog.html', courses=courses)


@app.route('/course/<code>')
def course_details(code):
    start_time = time.time()
    courses = load_courses()
    course = next((course for course in courses if course['code'] == code), None)
    # OpenTelemetry Tracing for Course Details
    with tracer.start_as_current_span("view_course_details") as span:
        if course:
            span.set_attribute("course_code", code)
            span.set_attribute("http.method", request.method)
            span.set_attribute("user.ip", request.remote_addr)
            span.add_event(f"Displaying details for course: {code}")
            # Track request counter and processing time
            request_counter.add(1, {"route": "/course"})
            operation_duration.record((time.time() - start_time) * 1000, {"route": "/course"})
            span.set_attribute("request_counter", request_counter)
            span.set_attribute("operation_duration", operation_duration)
        else:
            span.set_attribute("error", True)
            span.set_status(trace.Status(trace.StatusCode.ERROR, description=f"No course found for code {code}"))
            span.add_event(f"No course found with code: {code}")
            error_counter.add(1, {"route": "/course", "error": "course_not_found"})
            span.set_attribute("error count", error_counter)
            flash(f"No course found with code '{code}'.", "error")
            return redirect(url_for('course_catalog'))


    return render_template('course_details.html', course=course)

@app.route('/add_courses')
def add_courses():
    return render_template('add_courses.html')

@app.route('/add_course', methods=['GET', 'POST'])
def add_course():
    if request.method == 'POST':
        start_time = time.time()  # Track start time
        name = request.form.get('name')
        semester = request.form.get('semester')
        schedule = request.form.get('schedule')
        code = request.form.get('code')
        instructor = request.form.get('instructor')
        grade = request.form.get('grade')
        des = request.form.get('des')
        class_ = request.form.get('class')
        prerequisites = request.form.get('pre')

        # OpenTelemetry Tracing for Adding a Course
        with tracer.start_as_current_span("add_course") as span:
            # Validate inputs
            if not name or not instructor or not semester or not schedule or not code or not grade or not class_:
                span.set_attribute("error", True)
                span.add_event("Failed to add course. Missing fields.")
                flash('All fields are required!', 'error')
                error_counter.add(1, {"route": "/add_course", "error": "missing_fields"})
                span.set_attribute("error count", error_counter)
                app.logger.error('Course creation failed. Missing fields.')
                return redirect(url_for('add_course'))
            else:
                new_course = {
                    "code": code,
                    "name": name,
                    "instructor": instructor,
                    "semester": semester,
                    "schedule": schedule,
                    "classroom": class_,
                    "prerequisites": prerequisites,
                    "grading": grade,
                    "description": des
                }
                save_courses(new_course)
                
                # Add success event to trace
                span.set_attribute("course.code", code)
                span.add_event(f"Course {name} added successfully.")
                span.set_attribute("http.method", request.method)
                span.set_attribute("user.ip", request.remote_addr)
                span.set_status(trace.Status(trace.StatusCode.OK))
                span.set_attribute("course.name", name)
                span.set_attribute("course.instructor", instructor)
                span.set_attribute("course.semester", semester)
                flash('Course added successfully!', 'success')
                request_counter.add(1, {"route": "/add_course"})
                operation_duration.record((time.time() - start_time) * 1000, {"route": "/add_course"})
                
                # Track request counter and processing time
                span.set_attribute("request_counter", request_counter)
                span.set_attribute("operation_duration", operation_duration)

                app.logger.info(f'New course added: {name}, Instructor: {instructor}, Semester: {semester}')
                return redirect(url_for('course_catalog'))



    return render_template('course_catalog.html')

if __name__ == '__main__':
    app.run(debug=True)
