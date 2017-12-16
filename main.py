# GCP Schedule Start/Stop of instances
# Runs on Google App Engine
# Author: Paul Chapotet - paul@chapotet.com

import re
import jinja2
import webapp2
import datetime

from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

compute = discovery.build('compute','v1',
    credentials=GoogleCredentials.get_application_default())
resource_manager = discovery.build('cloudresourcemanager','v1',
    credentials=GoogleCredentials.get_application_default())

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader('templates'))

day_of_the_week = datetime.datetime.today().weekday() # Day of the week
regexp=r"(^[0-9]{1}[0-9]?[dw]?$)" # Regex to validate label value

def get_time():
    return datetime.datetime.now().strftime('[%Y-%m-%d %H:%M:%S] ')

def list_projects():
    """returns a list of projects"""
    projects = []
    request = resource_manager.projects().list()
    response = request.execute()
    projects_list = response.get('projects', {})
    for project in projects_list:
        if project['lifecycleState'] == "ACTIVE":
            projects.append(project['projectId'])
    return projects

def list_instances(project_id):
    """returns a list of dictionaries containing GCE instance data"""
    request = compute.instances().aggregatedList(project=project_id)
    response = request.execute()
    zones = response.get('items', {})
    instances = []
    for zone in zones.values():
        for instance in zone.get('instances', []):
            instances.append(instance)
    return instances

def start_instance(project, zone, instance):
    """starts instance"""
    request = compute.instances().start(project=project, zone=zone,
        instance=instance)
    response = request.execute()
    return response

def stop_instance(project, zone, instance):
    """stops instance"""
    request = compute.instances().stop(project=project, zone=zone,
        instance=instance)
    response = request.execute()
    return response

class CronPage(webapp2.RequestHandler):
    def get(self):
        status_list = []
        projects = list_projects()
        now = datetime.datetime.now()
        currentHour = now.hour
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write(get_time() +
            "Starting Start/Stop AppEngine application\r\n")

        # Loop over projects
        for project_id in projects:
            instances = list_instances(project_id)
            # Loop over instances in each project
            for instance in instances:
                if 'labels' in instance: # If we have labels on the instance
                    name=instance['name']
                    zone=instance['zone'].split('/')[-1]
                    for item in instance['labels']: # Loop over labels
                        key = item
                        value = instance['labels'][key]

                        # Startby label
                        if 'startby' in key and re.match(regexp, value):
                            requested_hour=int(re.findall('\\d+', value)[0])
                            if 0 <= requested_hour <= 23 and requested_hour == currentHour:
                                # Working days (0-4)
                                if 'd' in value and 0 <= day_of_the_week <= 4:
                                    start_instance(project_id,zone,name)
                                    self.response.write(get_time() +
                                        "Starting instance: " + name + "\r\n")
                                # Weekend days (5-6)
                                elif 'w' in value and 5 <= day_of_the_week <= 6:
                                    start_instance(project_id,zone,name)
                                    self.response.write(get_time() +
                                        "Starting instance: " + name + "\r\n")
                                # Everyday otherwise
                                elif 'w' not in value and 'd' not in value:
                                    start_instance(project_id,zone,name)
                                    self.response.write(get_time() +
                                        "Starting instance: " + name + "\r\n")

                        # Stopby label
                        if 'stopby' in key and re.match(regexp, value):
                            requested_hour=int(re.findall('\\d+', value)[0])
                            if 0 <= requested_hour <= 23 and requested_hour == currentHour:
                                # Working days (0-4)
                                if 'd' in value and 0 <= day_of_the_week <= 4:
                                    stop_instance(project_id,zone,name)
                                    self.response.write(get_time() +
                                        "Stopping instance: " + name + "\r\n")
                                # Weekend days (5-6)
                                elif 'w' in value and 5 <= day_of_the_week <= 6:
                                    stop_instance(project_id,zone,name)
                                    self.response.write(get_time() +
                                        "Stopping instance: " + name + "\r\n")
                                # Everyday otherwise
                                elif 'w' not in value and 'd' not in value:
                                    stop_instance(project_id,zone,name)
                                    self.response.write(get_time() +
                                        "Stopping instance: " + name + "\r\n")

class StatusPage(webapp2.RequestHandler):
    def get(self):
        status_list = []
        projects = list_projects()
        now = datetime.datetime.now()
        currentHour = now.hour
        # Loop over projects
        for project_id in projects:
            instances = list_instances(project_id)
            # Loop over instances in each project
            for instance in instances:
                startby="None"
                stopby="None"
                startbyvalid=False
                stopbyvalid=False
                if 'labels' in instance: # If we have labels on the instance
                    for item in instance['labels']: # Loop over labels
                        key = item
                        value = instance['labels'][key]
                        if 'startby' in key:
                            startby=value
                            if re.match(regexp, value):
                                requested_hour=int(re.findall('\\d+', value)[0])
                                if 0 <= requested_hour <= 23:
                                    startbyvalid=True
                        if 'stopby' in key:
                            stopby=value
                            if re.match(regexp, value):
                                requested_hour=int(re.findall('\\d+', value)[0])
                                if 0 <= requested_hour <= 23:
                                    stopbyvalid=True

                status_list.append({'project_id':project_id,
                    'instance_name':instance['name'],
                    'instance_zone':instance['zone'].split('/')[-1],
                    'instance_status':instance['status'],
                    'startby':startby,
                    'startbyvalid':startbyvalid,
                    'stopby':stopby,
                    'stopbyvalid':stopbyvalid})

        data = {}
        data['title'] = "GCP Start/Stop Status"
        data['date'] = currentHour
        data['status_list'] = status_list

        template = jinja_environment.get_template('status.html')
        self.response.out.write(template.render(data))

app = webapp2.WSGIApplication([
    ('/cron', CronPage),
    ('/status', StatusPage)
], debug=True)
