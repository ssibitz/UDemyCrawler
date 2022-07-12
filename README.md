# UDemyCrawler | Udemy Course Downloader (GUI)
Udemy crawler for backup courses to local drive and view the videos of the course(s) offline.
- A cross platform (Windows, Mac, Linux) desktop application for downloading Udemy Courses.

<img alt="MainScreen" height="300" src="/preview/MainScreen.png?raw=true"/>


### ***Important Note***:
 - Owner of this repository is not responsible for any misuse if you share your credentials with strangers.

### Warning
**Udemy has started to encrypt many of the course videos, so downloading them may be impossible/illegal because it involves decrypting DRM'd videos which opens up the author to DMCA takedowns/lawsuits. 
If you use UDemyCrawler and some/all videos are skipped, please don't open a new issue or comment that the issue still exists. 
All requests to bypass DRM/encryption will be ignored.**

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

## ***Tested on***
- Windows 10

## ***(Development) requirements***
- Build with python 3.9 in IntelliJ-IDE
- FFMPEG installed on windows from:<br>
**https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip**
- See requirements.txt for the needed dependencies 

## ***Features***
- Log into your UDemy account by using email/password as on the website
- Showing a simple view of "My learning"
- Under file/settings the user can set the download folder, don't re-download already existing video files and other things.
- By clicking on a course the course will be downloaded. 
- On downloading also this things will be generated: A playlist containing all videos in right order, a preview image, a short description and other files.
