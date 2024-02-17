## Getting Started with Local Development ##

 *Dependencies*
 The application was created using **Python 3.9**.  Later versions should funciton, but it is recommended to install this specific version.  
  - On Windows, [an installer (.msi) executable can be downloaded and run from here.](https://www.python.org/downloads/release/python-3912/)  On installation, do not select "Add Python to PATH" option if you have an existing installation (to avoid conflicts).  What you can then do is find the specific python.exe file created for this version, and execute it to create a virtual environment in your project's repository root folder.  The typical path and command line calls will follow this pattern, assuming your current working directory in command line is the meeting_picker project root folder:

  `"C:\Users\%USER%\AppData\Local\Programs\Python\Python39\python.exe" -m pip install virtualenv`

  `"C:\Users\alecz\AppData\Local\Programs\Python\Python39\python.exe" -m virtualenv .venv`

  - On Mac, [homebrew is recommended as a package manager](https://brew.sh/).  You can follow setup instructions on that site.  Once installed, setting up a specific Python installation is a straightforward matter:
```
brew install pyenv
pyenv install 3.9
pyenv local 3.9
python3 -m pip install virtualenv
python3 -m virtualenv .venv
```
  - On Linux (Debian/Ubuntu), you can use apt to install the specific version. Note that this will NOT supercede any existing Python3 version that you are using.
```
sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt update
sudo apt update
sudo apt install -y python3.9 python3-pip
python3.9 -m pip install -y virtualenv
python3.9 -m virtualenv .venv
```
 - In a command line tool (Windows CMD, git bash, sh, etc.), clone the master branch of the repository to a local folder.  This will save the code as a directory named "meeting_picker" in whatever directory within whichever directory your shell is working:
---

## Local Code Setup ##

 ### Windows ###

`git clone git@github.com:aleczoeller/meeting_picker.git`

Then:

```
cd meeting_picker
python -m virtualenv .venv
.venv\scripts\activate
pip install -r requirements.txt
```

- Create a virtual environment using the Python virtualenv library.  This allows for easy installation of all dependencies, and for running the application without interfering without other system resources.
### Linux/Mac ###

```git clone git@github.com:aleczoeller/meeting_picker.git```

Then:

```
cd meeting_picker
python3 -m virtualenv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
---

## Setting Up Environment Variables ##
---

There are a few way to do this, but the app is configured to look for an environments file names ".env" in the project base directory when it starts.  If you have been supplied one, use that, or populate the ".env_template" file, and rename it to ".env".  As an alternative, you may create these environments directly in your OS, but that's overkill for local testing. 

Your "HOSTNAME" variable may be retrieved from cPanel, or by pinging your website with a `ping` command.  The "DJANGO_SECRET" variable is required, and can be any arrangement of characters for testing purposes - this needs to be a sophisticated password in production though.  

The BMLT root server username and password may be retrieved from the administrator of the server, or via cPanel's file manager from the **autoconfig.inc.php** file in your root server's base directory.

This is how your environment variables can be set in cPanel's Python Apps section, if you are using a host that provides this feature:
![cPanel Environment Variables](meetingpicker/data/readme_envs.png)


---

## Running Test Server ##
When running locally, you need to whitelist your own IP address on your BMLT server in order to access the root MySQL database - see the associated section at the bottom of these directions.

Run the following commands to set up your local directory with the Django migrations and static files it needs to run a test server:

```
python manage.py migrate
python manage.py collectstatic --noinput
```

Finally:

`python manage.py runserver`

You can specify ports with the "runserver" command flag, [but if there are no conflicts with the default, the base app will now appear here](http://127.0.0.1:8000/nan/nan/nan/).

---

### White Listing Your IP Address with BMLT ###
You'll need to add your local machine's IP address to the white list on the host of the BMLT root server you are accessing.  This may be different than the host of the website that uses that BMLT! Contact your administrator if you don't have access.

You'll need to provide your machine's external IP address, this can be obtained from any machine using the following command, or from a website like [iplocation.net](iplocation.net).

`curl ifconfig.me`

In cPanel, go into the *Remote MySQL* section and enter the returned IP address, with a comment like "locaL testing *yournamehere*". You should be all set.

## Considerations for Production ##

- Create a cron job on your host server to refresh your meetings from the database source. Your credentials will be stored in the environments variables and/or .env file (if you have one).  The command to run is: `*/15 * * * * /home/nznaorg/repositories/meeting_picker/refresh_meetings.sh >> /home/nznaorg/repositories/meeting_picker/crontab.log 2>&1`  This will run the script every 15 minutes, and log the output to a file in the project's root directory.  To add a crontab, in the terminal on the host machine run `crontab -e` and paste the line at the bottom of the file.  Save and exit.
- If you have cPanel as a part of your hosting environment, the Python Apps section can be an effective method for deployment.  Your initial configuration can look like this:
![cPanel Python App](meetingpicker/data/readme_setup.png)