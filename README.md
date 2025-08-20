Airline Project 

XAMPP
1. Open manager-osx 
2. In the XAMPP control panel: start Apache, MySQL
3. Go to browser: http://localhost/phpmyadmin

create new database
* in phpMyAdmin, on the left panel, click the "New" button to create a new database
* name the database “database_name” and click Create

set created “database_name” as new database
* execute “USE database_name” to make the database the current one

import file into MySQL using phpMyAdmin
* go to the database you want to import the table into
* go to IMPORT tab
* click browse and find the sql file you want to import
* click go to execute the import (this will create the tables in ur database) 

run SQL queries
* go to the SQL tab
* type the query
* click go to execute

—

How to access the website
1. download repository from github 
2. run the following commands

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py (or python3 app.py)

questions
* is it standard for one to run this with python3 app.py and not just python app.py? can i stop it from doing so? does the fact that i have "alias python=/usr/bin/python3" in "nano ~/.zshrc"
* running the following in the venv "pip install -r requirements.txt" returned: WARNING: Retrying (Retry(total=4, connect=None, read=None, redirect=None, status=None)) after connection broken by 'NewConnectionError('<pip._vendor.urllib3.connection.HTTPSConnection object at 0x1069a5940>: Failed to establish a new connection: [Errno 8] nodename nor servname provided, or not known')': /simple/bcrypt/ ERROR: Could not find a version that satisfies the requirement bcrypt==4.2.1 (from versions: none)
ERROR: No matching distribution found for bcrypt==4.2.1