"""
 Copyright (c) 2018 Dynamic Phase, LLC All rights reserved.
 
 This program is free software; you can redistribute it and/or
 modify it under the terms of the GNU AFFERO GENERAL PUBLIC LICENSE
 Version 3 as published by the Free Software Foundation; either
 or (at your option) any later version.
 This library is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 General Public License for more details.

 You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
 along with this library; if not, write to the Free Software
 Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
"""

import logging

global_log_output = True
global_verbose = True
last_logstring = ""


def logstring(mystring, optional=None):
    global last_logstring
    global global_log_output
    global global_verbose
    if last_logstring == mystring and last_logstring == "com14 is indicated as Open":
        print("locations = {}".format(optional.locations))
        #raise Exception
    last_logstring = mystring
    if global_log_output:
        logging.info(mystring)
    if global_verbose:
        print(mystring, flush=True)

def setup_global_log_output(truetolog, verbose):
    global last_logstring
    global global_log_output
    global global_verbose
    last_logstring = ""
    global_log_ouptut = truetolog
    global_verbose = verbose
    print("sawthis...{}".format(last_logstring))
    logging.basicConfig(filename='./Wildcards.log', filemode='w',
        level=logging.DEBUG)
        
def logerr(mystring):
    if global_log_output:
        logging.exception(mystring)
    if global_verbose:
        print(mystring, flush=True)
