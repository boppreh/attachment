import email
import getpass
import imaplib
import os
import re
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from threading import Thread
from collections import namedtuple
import zipfile
import shutil

attachments_dir = 'attachments'
emails_seen_file = 'emails_seen.txt'
username = 'lucasboppre'
password = getpass.getpass("Enter your password: ")

Attachment = namedtuple('Attachment', ['id', 'sender', 'filename', 'contents'])
search_filter = 'has:attachment before:2013/01/01'# is:unread after:' + datetime.date.today().strftime('%Y/%m/%d')

def login(username, password, server='imap.gmail.com'):
    m = imaplib.IMAP4_SSL('imap.gmail.com')
    m.login(username, password)
    return m

def fetch_attachments(m=None):
    """
    Generator that returns a list of Attachment objects, each with 'email_id', 'sender', 'filename' and 'contents' attributes.
    """
    # Adapted from http://stackoverflow.com/a/642988/252218

    m.select('[Gmail]/All Mail') # Use m.list() to get all the mailboxes.
    #resp, items = m.search(None, '(UNSEEN)', '(SINCE "{}")'.format(datetime.date.today().strftime('%d-%b-%Y')))
    resp, items = m.search(None, '(UNSEEN)')
    #resp, items = m.uid('search', None, 'X-GM-RAW', search_filter)
    emails_ids = items[0].split()

    for email_id in emails_ids:
        resp, data = m.fetch(email_id, '(RFC822)') # Fetching the mail, "(RFC822)" means "get the whole stuff", but you can ask for headers only, etc.
        email_body = data[0][1]
        mail = email.message_from_string(email_body)

        # Check if any attachments at all.
        if mail.get_content_maintype() != 'multipart':
            continue

        try:
            # Considering a "From" field in the format
            # "Sender Name" <senderaddress@example.com>
            # this regex takes the address part.
            from_name = re.search('<(.+?)>', mail['From']).groups()[0]
        except:
            # If not possible, take the entire field.
            from_name = mail['From']

        for part in mail.walk():
            # Multipart are just containers, so we skip them.
            if part.get_content_maintype() == 'multipart':
                continue

            # Is this part an attachment?
            if part.get('Content-Disposition') is None:
                continue

            filename = part.get_filename()

            # If there is no filename, it's probably not a file attachment and should be ignored.
            if not filename:
                continue

            contents = part.get_payload(decode=True)
            yield Attachment(email_id + ' ' + filename, from_name, filename, contents)

def get_available_filename(base_dir, filename):
    """
    Returns a filename based on 'filename' that is not in use in 'base_dir'.
    """
    name, extension = os.path.splitext(filename)
    counter = 0

    while True:
        if counter == 0:
            path = os.path.join(base_dir, '{}{}'.format(name, extension))
        else:
            path = os.path.join(base_dir, '{} ({}){}'.format(name, counter, extension))

        if not os.path.isfile(path):
            return path

        counter += 1

def send_mail(address, subject, filename, extension, contents):
    # Adapted from http://stackoverflow.com/a/8243031/252218

    # Import smtplib for the actual sending function
    import smtplib

    # Import the email modules we'll need
    import email
    import email.mime.application

    # Create a text/plain message
    msg = email.mime.Multipart.MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = username + 'gmail.com'
    msg['To'] = address

    att = email.mime.application.MIMEApplication(contents, _subtype=extension)
    att.add_header('Content-Disposition','attachment', filename=filename)
    msg.attach(att)

    s = smtplib.SMTP('smtp.gmail.com:587')
    s.starttls()
    s.login(username, password)
    s.sendmail(username + 'gmail.com', [address], msg.as_string())
    s.quit()

def zipdir(path, zip_path):
    # Adapted from http://stackoverflow.com/a/1855118/252218.
    zip = zipfile.ZipFile(zip_path, 'w')
    basename = os.path.basename(path)
    for root, dirs, files in os.walk(path):
        for file in files:
            new_dir = root.replace(path, basename)
            zip.write(os.path.join(root, file), os.path.join(new_dir, file))
    zip.close()

class Sender(FileSystemEventHandler):
    def on_modified(self, event):
        self.on_created(event)

    def on_moved(self, event):
        self.on_created(event)

    def on_created(self, event):
        path = event.src_path.replace('\\', '/')

        try:
            address, attachment_name = re.search('to-send/(.+?)/(.+)', path).groups()
        except:
            return

        if not '@' in path or not os.path.exists(path) or not address or not attachment_name:
            return

        if os.path.isdir(path):
            zipdir(path, path + '.zip')
            shutil.rmtree(path, ignore_errors=True)
            # Creating the zip file should trigger another event.
        else:
            name, extension = os.path.splitext(attachment_name)
            contents = open(path).read()
            subject = name.title().replace('_', ' ').replace('-', ' ')
            try:
                send_mail(address, subject, attachment_name, extension[1:], contents)
            except:
                # Gmail may block some files types, such as .exe or even zips
                # containing blacklisted types. By renaming the file to
                # something else most filters can be bypassed.
                send_mail(address, subject, attachment_name + '.rename-me', extension[1:], contents)

            os.remove(path)            

def watch_dir(dir_path):
    full_path = os.path.abspath(dir_path)
    observer = Observer()
    observer.schedule(Sender(), path=full_path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

if __name__ == '__main__':
    from background import tray
    tray('Att', 'attachment.png')

    if not os.path.isdir(attachments_dir):
        os.makedirs(attachments_dir)

    emails_seen_path = os.path.join(attachments_dir, emails_seen_file)
    if os.path.isfile(emails_seen_path):
        emails_seen = open(emails_seen_path, 'r').read().split('\n')
    else:
        emails_seen = []

    to_send_dir = os.path.join(attachments_dir, 'to-send')
    if not os.path.isdir(to_send_dir):
        os.makedirs(to_send_dir)

    watcher = Thread(target=watch_dir, args=[to_send_dir])
    watcher.daemon = True
    watcher.start()

    m = login(username, password)

    while True:
        for attachment in fetch_attachments(m):
            if attachment.id in emails_seen:
                continue

            sender_dir = os.path.join(attachments_dir, 'received', attachment.sender)
            if not os.path.isdir(sender_dir):
                os.makedirs(sender_dir)

            attachment_path = get_available_filename(sender_dir, attachment.filename)
            if attachment_path.endswith('.rename-me'):
                attachment_path = attachment_path.replace('.rename-me', '')

            with open(attachment_path, 'wb') as attachment_file:
                attachment_file.write(attachment.contents)

            #if attachment_path.endswith('.zip'):
            #    print 'I think this should be unzipped.'

            emails_seen.append(attachment.id)

        # Update file with emails seen.
        open(emails_seen_path, 'w').write('\n'.join(emails_seen))

        time.sleep(5)
