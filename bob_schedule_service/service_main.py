#!/usr/bin/python3
""" service_main.py:
"""

# Import Required Libraries (Standard, Third Party, Local) ********************
import asyncio
import copy
import datetime
import logging
import os
import sys
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bob_schedule_service.msg_processing import create_heartbeat_msg
from bob_schedule_service.msg_processing import process_heartbeat_msg
from bob_schedule_service.msg_processing import process_get_device_scheduled_state_msg


# Authorship Info *************************************************************
__author__ = "Christopher Maue"
__copyright__ = "Copyright 2017, The RPi-Home Project"
__credits__ = ["Christopher Maue"]
__license__ = "GPL"
__version__ = "1.0.0"
__maintainer__ = "Christopher Maue"
__email__ = "csmaue@gmail.com"
__status__ = "Development"


# Internal Service Work Task **************************************************
class MainTask(object):
    def __init__(self, logger=None, **kwargs):
        # Configure logger
        self.logger = logger or logging.getLogger(__name__)
        
        # Define instance variables
        self.ref_num = None
        self.msg_in_queue = None
        self.msg_out_queue = None
        self.schedule = []
        self.service_addresses = []
        self.message_types = []
        self.last_check_hb = datetime.datetime.now()
        self.sleep_time = 0.2
        self.out_msg = str()
        self.out_msg_list = []
        self.next_msg = str()
        self.next_msg_split = []
        self.msg_source_addr = str()
        self.msg_source_port = str()
        self.msg_type = str()
        self.destinations = []

        # Map input variables
        if kwargs is not None:
            for key, value in kwargs.items():
                if key == "ref":
                    self.ref_num = value
                    self.logger.debug('Ref number generator set during __init__ '
                                      'to: %s', self.ref_num)
                if key == "schedule":
                    self.schedule = value
                    self.logger.debug('Schedule set during __init__ '
                                      'to: %s', self.schedule)
                if key == "msg_in_queue":
                    self.msg_in_queue = value
                    self.logger.debug('Message in queue set during __init__ '
                                      'to: %s', self.msg_in_queue)
                if key == "msg_out_queue":
                    self.msg_out_queue = value
                    self.logger.debug('Message out queue set during __init__ '
                                      'to: %s', self.msg_out_queue)
                if key == "service_addresses":
                    self.service_addresses = value
                    self.logger.debug('Service address list set during __init__ '
                                      'to: %s', self.service_addresses)
                if key == "message_types":
                    self.message_types = value
                    self.logger.debug('Message type list set during __init__ '
                                      'to: %s', self.message_types)


    @asyncio.coroutine
    def run(self):
        """ task to handle the work the service is intended to do """
        self.logger.info('Starting schedule service main task')

        while True:
            # Initialize result list
            self.out_msg_list = []
            self.sleep_time = 0.2

            # INCOMING MESSAGE HANDLING
            if self.msg_in_queue.qsize() > 0:
                self.sleep_time = 0.01
                self.logger.debug('Getting Incoming message from queue')
                self.next_msg = self.msg_in_queue.get_nowait()
                self.logger.debug('Message pulled from queue: [%s]', self.next_msg)

                # Determine message type
                self.next_msg_split = self.next_msg.split(',')
                if len(self.next_msg_split) >= 6:
                    self.logger.debug('Extracting source address and message type')
                    self.msg_source_addr = self.next_msg_split[3]
                    self.msg_source_port = self.next_msg_split[4]
                    self.msg_type = self.next_msg_split[5]
                    self.logger.debug('Source Address: %s', self.msg_source_addr)
                    self.logger.debug('Source Port: %s', self.msg_source_addr)
                    self.logger.debug('Message Type: %s', self.msg_type)

                # Service Check (heartbeat)
                if self.msg_type == self.message_types['heartbeat']:
                    self.logger.debug('Message is a heartbeat')
                    self.out_msg_list = process_heartbeat_msg(
                        self.logger,
                        self.ref_num,
                        self.next_msg,
                        self.message_types)

                # Device scheduled command checks
                if self.msg_type == self.message_types['get_device_scheduled_state']:
                    self.logger.debug('Message is a get device scheduled state message')
                    self.out_msg_list = process_get_device_scheduled_state_msg(
                        self.logger,
                        self.ref_num,
                        self.schedule,
                        self.next_msg,
                        self.message_types)

                # Que up response messages in outgoing msg que
                if len(self.out_msg_list) > 0:
                    self.logger.debug('Queueing response message(s)')
                    for self.out_msg in self.out_msg_list:
                        self.msg_out_queue.put_nowait(copy.copy(self.out_msg))
                        self.logger.debug('Response message [%s] successfully queued',
                                          self.out_msg)                        


            # PERIODIC TASKS
            # Periodically send heartbeats to other services
            if datetime.datetime.now() >= (self.last_check_hb + datetime.timedelta(seconds=60)):
                self.destinations = [
                    (self.service_addresses['automation_addr'],
                     self.service_addresses['automation_port'])
                ]
                self.out_msg_list = create_heartbeat_msg(
                    self.logger,
                    self.ref_num,
                    self.destinations,
                    self.service_addresses['schedule_addr'],
                    self.service_addresses['schedule_port'],
                    self.message_types)

                # Que up response messages in outgoing msg que
                if len(self.out_msg_list) > 0:
                    self.logger.debug('Queueing response message(s)')
                    for self.out_msg in self.out_msg_list:
                        self.msg_out_queue.put_nowait(copy.copy(self.out_msg))
                        self.logger.debug('Response message [%s] successfully queued',
                                          self.out_msg)

                # Update last-check
                self.last_check_hb = datetime.datetime.now()

            # Yield to other tasks for a while
            yield from asyncio.sleep(self.sleep_time)
