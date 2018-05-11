# smugcli
Command line tool for SmugMug, useful for automatically synchronizing a local folder hierarchy with a SmugMug account.

Implemented using the V2 API and tested with Python 2.7.10.

# Prerequisites
Depends on the following Python libraries:

 * For authentification and communication with SmugMug:
   * bottle
   * rauth
   * requests
   * requests_oauthlib

 * For parsing metadata from local files:
   * hachoir_core
   * hachoir_parser
   * hachoir_metadata

 * To run unit-tests:
   * parameterized
   * mock
   * responses

You may install any missing library using `pip` (e.g. `pip install requests`)

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
Note that smugcli can also be used to access other public SmugMug account by using the `--user` argument:
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
$ ./smugcli.py sync local/folder --target remote/folder
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

The sync command can be re-executed to update the remote Albums in the event that the local files might have been updated. Only the files that changed will be re-uploaded. To exclude paths from the sync operation, run the command:
```
$ ./smugcli.py ignore local/folder/export-tmp
```

To undo this operation, you can run:
```
$ ./smugcli.py include local/folder/export-tmp
```

# Running the tests
PLEASE READ, RUN UNIT TESTS AT YOUR OWN RISKS: smugcli's unit-tests use the logged-in user account to do run actual commands on SmugMug. All operations *should* be performed in a `__smugcli_unit_tests__` subfolder in the SmugMug account's root. This folder *should* be deleted automatically when/if the test completes. If in doubt, do `smugcli.py logout && smugcli.py login` and use a test account.

Run all unit tests by running:
```
$ ./run_tests.py
```

Individual tests can be ran by doing:
```
$ ./run_tests.py module[.class_name[.test_name]]
```
for instance:
```
$ ./run_tests.py end_to_end_test  # Runs all tests in module end_to_end_test.
$ ./run_tests.py end_to_end_test.EndToEndTest  # Runs all tests in class EndToEndTest.
$ ./run_tests.py end_to_end_test.EndToEndTest.test_mkdir  # Runs a single test.
```

SmugMug is slow, so to speed up iterations while changing code, all HTTP requests are cached on disk and replayed on subsequent runs. The first test run will take a while, but the second one should take about a second. When updating tests however, the cached HTTP request may no longer match the new test code. Reset the cache by using `--reset_cache`:
```
$ ./run_tests.py end_to_end_test.EndToEndTest.test_mkdir --reset_cache
```
