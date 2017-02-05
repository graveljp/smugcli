# smugcli
Command line tool for SmugMug, useful for automatically synchronizing a local folder hierarchy with a SmugMug account.

Implemented using the V2 API and tested with Python 2.7.10.

# Sample usage

To use this command line tool, you will need to request your own API key by visiting https://api.smugmug.com/api/developer/apply. Using your key and secret, loging to smugcli using the following command:
```
$ ./smugcli.py login --key=<key> --secret=<secret>
```

This is a one time operation. From this point on, smugcli will be able to access your SmugMug account. To logout, run the command: `$ ./smugcli.py logout`

You can list the content of your SmugMug account by doing:
```
$ ./smugcli.py ls
 Photography
 Portfolio
 Other
 
$ ./smugcli.py ls Photography
 2014
 2015
 2016

 
$ ./smugcli.py ls Photography/2015
 Photoshoot with Dave
```
All commands can also be executed against another user's account. For instance:
```
$ ./smugcli.py ls -u <username>
```

Folders can be created by using the `mkdir` command:
```
$ ./smugcli.py mkdir Photography/2017
```

Similarily, albums can be created by doing:
```
$ ./smugcli.py mkalbum 'Photography/2017/My new album'
```

To upload photos to an album, run:
```
$ ./smugcli.py upload local/folder/*.jpg 'Photography/2017/My new album'
```

Finally, the nicest feature of all, you can synchronize a whole local folder hierarchy to your SmugMug account using the `sync` command:
```
$ ./smugcli.py sync local/folder --target remove/folder
Making folder remote/folder/2015
Making album remote/folder/2015/2015-08-03, Mary's Wedding
Uploading local/folder/2015/2015-08-03, Mary's Wedding/DSC_0001.JPG
Uploading local/folder/2015/2015-08-03, Mary's Wedding/DSC_0002.JPG
Uploading local/folder/2015/2015-08-03, Mary's Wedding/DSC_0003.JPG
...
Making album remote/folder/2015/2015-09-10, Andy's Photoshoot
Uploading local/folder/2015/2015-09-10, Andy's Photoshoot/DSC_0043.JPG
Uploading local/folder/2015/2015-09-10, Andy's Photoshoot/DSC_0052.JPG
...
```

The sync command can be re-executed to update the remote Albums in the event that the local files might have been updated. Only the files that changed will be re-uploaded. To exclute files from the sync operation, run the command:
```
$ ./smugcli.py ignore local/folder/export-tmp
```

To undo this operation, you can run:
```
$ ./smugcli.py include local/folder/export-tmp
```
