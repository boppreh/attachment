attachment
==========

`attachment` is a project to bring email attachments closer to the owner,
interfacing directly with the filesystem.

GMail support only for the moment.


Receiving
---------

While the program is running your email is polled periodically, waiting for new
emails with attachments. Whenever a new attachment is detected, it is
automatically downloaded to your computer and grouped by sender. If you wish
you can enable automatic decompression of archive files, but bear in mind this
opens you to zipbomb attacks.


Sending
-------

To send an attachment to another user you just copy the desired file or folder
to the respective user 'to-send' directory. Folders are automatically
compressed and forbidden files (like executables) are renamed to avoid
detection (if the other side is using `attachment` too, the renaming is
automatically undone on the other side).

After the file has been sent and the confirmation arrived, *the file you sent
is removed*.
