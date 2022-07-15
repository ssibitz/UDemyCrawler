# UDemyCrawler | Udemy Course Downloader (Python GUI)
- A desktop application for downloading Udemy Courses to a local path. 

<img alt="MainScreen" height="300" src="/preview/MainScreen.png?raw=true"/>

### ***Important Note***:
 - Owner of this repository is not responsible for any misuse if you share your credentials with strangers.

### Warning
<div style="color:red;font-weight:bold;">
Udemy has started to encrypt many of the course videos, so downloading them may be impossible/illegal because it involves decrypting DRM'd videos which opens up the author to DMCA takedowns/lawsuits. 
If you use UDemyCrawler and some/all videos are skipped, please don't open a new issue or comment that the issue still exists. 
All requests to bypass DRM/encryption will be ignored.
</div>

### Disclaimer:
This software is intended to help you download Udemy courses for personal use only. 
Sharing the content of your subscribed courses is strictly prohibited under Udemy Terms of Use. 
Each and every course on Udemy is subjected to copyright infringement.
This software does not magically download any paid course available on Udemy, 
you need to provide your Udemy login credentials to download the courses you have enrolled in. 
UDemyCrawler downloads the lecture videos by simply automate the webpage of UDemy and use the original API as used on the website, 
so you can also do the same manually. 
Many download managers use same method to download videos on a web page. 
This app only automates the process of a user doing this manually in a web browser.


## ***External libraries, tools and licenses used:***
- FontAweSome for desktop icons:<br/>
https://fontawesome.com/
- FFMPEG for combining and converting videos:<br/>
https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip

## ***Tested on***
- Windows 10

## ***(Development) requirements***
- Build with python 3.9 in IntelliJ-IDE
- See requirements.txt for the needed dependencies 

## ***Features***
- Log into your UDemy account by using your email/password as on the website
- Showing a simple view of "My learning"
- Simple user settings which also allows to automatically download/unzip latest version of FFMPEG 
- By clicking on a course the course will be downloaded:<br/>
 All <b>non protected</b> videos and articles as html files will be downloaded
- Before the course will be downloaded it checks if the course contains <b>protected</b> videos.<br/>You can cancel here if you don't won't to download only the <b>non protected</b> parts of the course!
- Download can be canceled and resumed later
- Generate a playlist with all videos
- Combine all videos of a course into one video - so its easier to view on eg a TV over a NAS