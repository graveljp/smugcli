"""Integration test invoking SmugCLI against the real SmugMug service."""

import unittest
import os

import integration_test_base
import io_expectation as expect

from smugcli import version


class EndToEndTest(integration_test_base.IntegrationTestBase):
  """Integration test invoking SmugCLI against the real SmugMug service."""

  def test_version(self):
    """Test for `smugcli --version`."""
    self._do('--version', 'Version: ' + version.__version__)

  def test_get(self):
    """Test for `smugcli get`."""
    self._do('get \\/api\\/v2\\/user',
             expect.Somewhere(
                 ['"Code": 200,',
                  '"Message": "Ok",']))

  def test_ls(self):
    """Test for `smugcli ls`."""
    # Fails if node doesn't exists.
    self._do('ls {root}',
             '"{root}" not found in "".')
    self._do('ls {root}/foo',
             '"{root}" not found in "".')

    # Works if node exists:
    self._do('mkdir -p {root}/foo/bar {root}/foo/baz')
    self._do('ls {root}',
             'foo')
    self._do('ls {root}/foo',
             ['bar',
              'baz'])

    # Lists root node by default:
    self._do('ls', expect.Somewhere('{root}'))

    # Shows full node JSON info in -l mode:
    self._do('ls -l {root}',
             expect.Somewhere('"Name": "foo",'))

    # Lists other user's folder:
    self._do('ls -u cmac',
             expect.Somewhere('Photography'))

    # Query a field from the node's JSON:
    self._do('ls -q "WebUri" {root}',
             expect.Url(expect.Regex(r'https://.*/Foo')))

    # Invalid query string:
    self._do('ls -q foo^bar {root}',
             expect.Contains('Invalid query string'))

    # Gracefully handle folders that are actually files.
    self._do('upload -p {testdata}/SmugCLI_1.jpg {root}/album')
    self._do(
        'ls {root}/album/SmugCLI_1.jpg/foo',
        '"/{root}/album/SmugCLI_1.jpg" is a file, it can\'t have child nodes.')

  def test_mkdir(self):
    """Test for `smugcli mkdir`."""
    # Missing parent.
    self._do('mkdir {root}/foo',
             '"{root}" not found in "".')

    # Creating root folder.
    self._do('mkdir {root}',
             'Creating folder "{root}".')

    # Cannot create existing folder.
    self._do('mkdir {root}',
             'Path "{root}" already exists.')

    # Missing sub-folder parent.
    self._do('mkdir {root}/foo/bar/baz',
             '"foo" not found in "/{root}".')

    # Creates all missing parents.
    self._do('mkdir -p {root}/foo/bar/baz',
             ['Creating folder "{root}/foo".',
              'Creating folder "{root}/foo/bar".',
              'Creating folder "{root}/foo/bar/baz".'])

    # Check that all folders were properly created.
    self._do('ls {root}/foo/bar',
             'baz')
    self._do('ls {root}/foo/bar/baz',
             [])  # Folder exists, but is empty.

    # Can create many folders in one command.
    self._do('mkdir {root}/buz {root}/biz',
             ['Creating folder "{root}/buz".',
              'Creating folder "{root}/biz".'])

    self._do('mkdir {root}/baz/biz {root}/buz {root}/baz',
             ['"baz" not found in "/{root}".',
              'Path "{root}/buz" already exists.',
              'Creating folder "{root}/baz".'])

    self._do('ls {root}',
             ['baz',
              'biz',
              'buz',
              'foo'])

    # Can't create a folder in an album.
    self._do('mkalbum {root}/album')
    self._do('mkdir {root}/album/folder',
             ['Folders can only be created in folders.',
              '"album" is of type "Album"'])

    # Can't create folders as a child of a file.
    self._do('upload {testdata}/SmugCLI_1.jpg {root}/album')
    self._do(
        'mkdir {root}/album/SmugCLI_1.jpg/folder',
        '"/{root}/album/SmugCLI_1.jpg" is a file, it can\'t have child nodes.')

  def test_mkdir_privacy(self):
    """Test the `--privacy` option of `smugcli mkdir`."""
    self._do('mkdir -p {root}/default/folder')
    self._do('ls -l {root}/default',
             expect.Somewhere('"Privacy": "Public",'))

    self._do('mkdir -p {root}/public/folder --privacy=public')
    self._do('ls -l {root}/public',
             expect.Somewhere('"Privacy": "Public",'))

    self._do('mkdir -p {root}/unlisted/folder --privacy=unlisted')
    self._do('ls -l {root}/unlisted',
             expect.Somewhere('"Privacy": "Unlisted",'))

    self._do('mkdir -p {root}/private/folder --privacy=private')
    self._do('ls -l {root}/private',
             expect.Somewhere('"Privacy": "Private",'))

  def test_mkdir_folder_depth_limits(self):
    """Test SmugMug's folder nesting limit when using `smugcli mkdir`."""
    # Can't create more than 5 folder deep.
    self._do('mkdir -p {root}/1/2/3/4',
             ['Creating folder "{root}".',
              'Creating folder "{root}/1".',
              'Creating folder "{root}/1/2".',
              'Creating folder "{root}/1/2/3".',
              'Creating folder "{root}/1/2/3/4".'])
    self._do('mkdir -p {root}/1/2/3/4/5',
             ['Cannot create "{root}/1/2/3/4/5", SmugMug does not support '
              'folder more than 5 level deep.'])
    self._do('mkalbum -p {root}/1/2/3/4/5',
             ['Creating album "{root}/1/2/3/4/5".'])

  def test_mkalbum(self):
    """Test for `smugcli mkalbum`."""
    # Missing parent.
    self._do('mkalbum {root}/folder/album',
             ['"{root}" not found in "".'])

    # Create all missing folders.
    self._do('mkalbum -p {root}/folder/album',
             ['Creating folder "{root}".',
              'Creating folder "{root}/folder".',
              'Creating album "{root}/folder/album".'])

    # Can't create a album in an album.
    self._do('mkalbum {root}/album')
    self._do('mkalbum {root}/album/folder',
             ['Albums can only be created in folders.',
              '"album" is of type "Album"'])

    # Can't create albums as a child of a file.
    self._do('upload {testdata}/SmugCLI_1.jpg {root}/album')
    self._do(
        'mkalbum {root}/album/SmugCLI_1.jpg/folder',
        '"/{root}/album/SmugCLI_1.jpg" is a file, it can\'t have child nodes.')

  def test_mkalbum_privacy(self):
    """Test the `--privacy` option of `smugcli mkalbum`."""
    self._do('mkalbum -p {root}/default/album')
    self._do('ls -l {root}/default',
             expect.Somewhere('"Privacy": "Public",'))

    self._do('mkalbum -p {root}/public/album --privacy=public')
    self._do('ls -l {root}/public',
             expect.Somewhere('"Privacy": "Public",'))

    self._do('mkalbum -p {root}/unlisted/album --privacy=unlisted')
    self._do('ls -l {root}/unlisted',
             expect.Somewhere('"Privacy": "Unlisted",'))

    self._do('mkalbum -p {root}/private/album --privacy=private')
    self._do('ls -l {root}/private',
             expect.Somewhere('"Privacy": "Private",'))

  def test_rmdir(self):
    """Test for `smugcli rmdir`."""
    # Create a test folder hierarchy.
    self._do('mkdir -p {root}/foo/bar/baz')
    self._do('mkdir -p {root}/buz')

    # Can't remove non-existing folders.
    self._do('rmdir {root}/foo/bar/baz/buz',
             ['Folder or album "{root}/foo/bar/baz/buz" not found.'])

    # Can't remove non-empty folders.
    self._do('rmdir {root}/foo/bar',
             ['Cannot delete folder: "{root}/foo/bar" is not empty.'])

    # Can delete simple folder.
    self._do('rmdir {root}/foo/bar/baz',
             ['Deleting "{root}/foo/bar/baz".'])
    self._do('ls {root}/foo',
             ['bar'])
    self._do('ls {root}/foo/bar',
             [])  # Folder exists, but is empty.

    # Can delete folder and all its non-empty parents.
    self._do('rmdir -p {root}/foo/bar',
             ['Deleting "{root}/foo/bar".',
              'Deleting "{root}/foo".',
              'Cannot delete folder: "{root}" is not empty.'])

    self._do('ls {root}/foo',
             ['"foo" not found in "/{root}".'])
    self._do('ls {root}',
             ['buz'])

    # Can't rmdir a file.
    self._do('upload -p {testdata}/SmugCLI_1.jpg {root}/album')
    self._do('rmdir {root}/album/SmugCLI_1.jpg',
             'Cannot delete file "{root}/album/SmugCLI_1.jpg", rmdir can only '
             'delete empty folder or album.')

  def test_rm_file(self):
    """Test `smugcli rm` for file nodes."""
    self._do('upload -p '
             '{testdata}/SmugCLI_1.jpg '
             '{testdata}/SmugCLI_2.jpg '
             '{root}/album')

    # Handles file not found errors.
    self._do('rm {root}/does_not_exists',
             ['"{root}/does_not_exists" not found.'])

    # Asks for confirmation by default.
    self._do('rm {root}/album/SmugCLI_1.jpg',
             ['Remove file "{root}/album/SmugCLI_1.jpg"? ',
              expect.Reply('n')])
    self._do('ls {root}/album',
             ["SmugCLI_1.jpg",
              "SmugCLI_2.jpg"])

    self._do('rm {root}/album/SmugCLI_1.jpg',
             ['Remove file "{root}/album/SmugCLI_1.jpg"? ',
              expect.Reply('y'),
              'Removing file "{root}/album/SmugCLI_1.jpg".'])
    self._do('ls {root}/album',
             ["SmugCLI_2.jpg"])

  def test_rm_album(self):
    """Test `smugcli rm` for album nodes."""
    self._do('upload -p '
             '{testdata}/SmugCLI_1.jpg '
             '{root}/album1')
    self._do('upload -p '
             '{testdata}/SmugCLI_1.jpg '
             '{root}/album2')

    # Can't remove album by default.
    self._do('rm {root}/album1',
             ['Cannot remove, "{root}/album1" is of type "Album".'])
    self._do('ls {root}/album1', ["SmugCLI_1.jpg"])

    # Albums can be removed in recursive mode, ask for confirmation by default.
    self._do('rm -r {root}/album1',
             ['Remove album "{root}/album1"? ',
              expect.Reply('n')])
    self._do('ls {root}', ['album1', 'album2'])
    self._do('ls {root}/album1', ["SmugCLI_1.jpg"])

    self._do('rm -r {root}/album1',
             ['Remove album "{root}/album1"? ',
              expect.Reply('y'),
              'Removing album "{root}/album1".'])
    self._do('ls {root}', ['album2'])

    # Albums and their content can be removed in recursive mode.
    # Operation can be forced.
    self._do('rm -r -f {root}/album2',
             ['Removing album "{root}/album2".'])
    self._do('ls {root}', [])

  def test_rm_folder(self):
    """Test `smugcli rm` for folder/album nodes."""
    self._do('mkdir -p {root}/foo/bar/baz')
    self._do('upload -p '
             '{testdata}/SmugCLI_1.jpg '
             '{root}/dir/album')

    # Can't remove directory by default.
    self._do('rm {root}/foo/bar/baz',
             ['Cannot remove, "{root}/foo/bar/baz" is of type "Folder".'])
    self._do('ls {root}/foo/bar', ["baz"])

    # Can remove directory in recursive mode, ask for confirmation by default.
    self._do('rm -r {root}/foo/bar/baz',
             ['Remove folder "{root}/foo/bar/baz"? ',
              expect.Reply('n')])
    self._do('ls {root}/foo/bar', ["baz"])

    self._do('rm -r {root}/foo/bar/baz',
             ['Remove folder "{root}/foo/bar/baz"? ',
              expect.Reply('y'),
              'Removing folder "{root}/foo/bar/baz".'])
    self._do('ls {root}/foo/bar', [])

    # Can remove non-empty directory in recursive mode:
    self._do('rm -f -r {root}/foo',
             ['Removing folder "{root}/foo".'])

  def test_rm_confirmations(self):
    """Test confirmation messages for `smugcli rm`."""
    self._do('upload -p '
             '{testdata}/SmugCLI_1.jpg '
             '{testdata}/SmugCLI_2.jpg '
             '{testdata}/SmugCLI_3.jpg '
             '{testdata}/SmugCLI_4.jpg '
             '{root}/album')

    # Reject operation.
    self._do('rm {root}/album/SmugCLI_1.jpg',
             ['Remove file "{root}/album/SmugCLI_1.jpg"? ',
              expect.Reply('n')])
    self._do('rm {root}/album/SmugCLI_1.jpg',
             ['Remove file "{root}/album/SmugCLI_1.jpg"? ',
              expect.Reply('anything')])
    self._do('ls {root}/album',
             ["SmugCLI_1.jpg",
              "SmugCLI_2.jpg",
              "SmugCLI_3.jpg",
              "SmugCLI_4.jpg"])

    # Accept operation.
    self._do('rm {root}/album/SmugCLI_1.jpg',
             ['Remove file "{root}/album/SmugCLI_1.jpg"? ',
              expect.Reply('y'),
              'Removing file "{root}/album/SmugCLI_1.jpg"'])
    self._do('ls {root}/album',
             ["SmugCLI_2.jpg",
              "SmugCLI_3.jpg",
              "SmugCLI_4.jpg"])

    self._do('rm {root}/album/SmugCLI_2.jpg',
             ['Remove file "{root}/album/SmugCLI_2.jpg"? ',
              expect.Reply('yes'),
              'Removing file "{root}/album/SmugCLI_2.jpg"'])
    self._do('ls {root}/album',
             ["SmugCLI_3.jpg",
              "SmugCLI_4.jpg"])

    self._do('rm {root}/album/SmugCLI_3.jpg',
             ['Remove file "{root}/album/SmugCLI_3.jpg"? ',
              expect.Reply('YES'),
              'Removing file "{root}/album/SmugCLI_3.jpg"'])
    self._do('ls {root}/album',
             ["SmugCLI_4.jpg"])

  def test_rm_multiple_nodes(self):
    """Test that `smugcli rm` can remove multiple nodes in one command."""
    self._do('upload -p '
             '{testdata}/SmugCLI_1.jpg '
             '{testdata}/SmugCLI_2.jpg '
             '{testdata}/SmugCLI_3.jpg '
             '{testdata}/SmugCLI_4.jpg '
             '{root}/album1')
    self._do('mkalbum -p {root}/album2')
    self._do('mkdir -p {root}/dir')

    # Can remove multiple files.
    self._do('rm {root}/album1/SmugCLI_1.jpg {root}/album1/SmugCLI_2.jpg',
             ['Remove file "{root}/album1/SmugCLI_1.jpg"? ',
              expect.Reply('n'),
              'Remove file "{root}/album1/SmugCLI_2.jpg"? ',
              expect.Reply('y'),
              'Removing file "{root}/album1/SmugCLI_2.jpg".'])
    self._do('ls {root}/album1',
             ["SmugCLI_1.jpg", "SmugCLI_3.jpg", "SmugCLI_4.jpg"])

    # Can remove files, but won't remove folders/albums.
    self._do('rm {root}/album1/SmugCLI_1.jpg {root}/album2 {root}/dir',
             ['Remove file "{root}/album1/SmugCLI_1.jpg"? ',
              expect.Reply('y'),
              'Removing file "{root}/album1/SmugCLI_1.jpg".',
              'Cannot remove, "{root}/album2" is of type "Album".',
              'Cannot remove, "{root}/dir" is of type "Folder".'])
    self._do('ls {root}/album1',
             ["SmugCLI_3.jpg", "SmugCLI_4.jpg"])
    self._do('ls {root}',
             ["dir", "album1", "album2"])

    # Folders/albums can be removed in recursive mode:
    self._do('rm -r {root}/album1 {root}/album2 {root}/dir',
             ['Remove album "{root}/album1"? ',
              expect.Reply('no'),
              'Remove album "{root}/album2"? ',
              expect.Reply('yes'),
              'Removing album "{root}/album2".',
              'Remove folder "{root}/dir"? ',
              expect.Reply('no')])
    self._do('ls {root}',
             ["dir", "album1"])

    # Removing multiple nodes can be forced:
    self._do('rm -r -f {root}/album1 {root}/dir',
             ['Removing album "{root}/album1".',
              'Removing folder "{root}/dir".'])
    self._do('ls {root}',
             [])

  def test_upload(self):
    """Test for `smugcli upload`."""
    # Can't upload to non-existing album.
    self._do('upload {testdata}/SmugCLI_1.jpg {root}/folder/album',
             ['Album not found: "{root}/folder/album".'])

    # Can't upload to folders.
    self._do('mkdir -p {root}/folder')
    self._do('upload {testdata}/SmugCLI_1.jpg {root}/folder',
             ['Cannot upload images in node of type "Folder".'])

    # Can upload to album.
    self._do('mkalbum -p {root}/folder/album')
    self._do(
        'upload {testdata}/SmugCLI_1.jpg {root}/folder/album',
        ['Uploading "{testdata}/SmugCLI_1.jpg" to "{root}/folder/album"...'])
    self._do('ls {root}/folder/album', ['SmugCLI_1.jpg'])

    # Can't upload duplicate.
    self._do(
        'upload {testdata}/SmugCLI_1.jpg {root}/folder/album',
        ['Skipping "{testdata}/SmugCLI_1.jpg", file already exists in Album '
         '"{root}/folder/album".'])
    self._do('ls {root}/folder/album', ['SmugCLI_1.jpg'])

    # Can't upload over existing file.
    self._do(
        'upload {testdata}/SmugCLI_2.jpg {root}/folder/album/SmugCLI_1.jpg',
        ['Cannot upload images in node of type "File".'])
    self._do('ls {root}/folder/album', ['SmugCLI_1.jpg'])

    # Can upload multiple files
    self._do(
        'upload {testdata}/Sm?gCLI_1.* {testdata}/SmugCLI_2.jpg '
        '{root}/folder/album',
        ['Uploading "{testdata}/SmugCLI_1.gif" to "{root}/folder/album"...',
         'Uploading "{testdata}/SmugCLI_1.heic" to "{root}/folder/album"...',
         'Skipping "{testdata}/SmugCLI_1.jpg", file already exists in Album '
         '"{root}/folder/album".',
         'Uploading "{testdata}/SmugCLI_1.png" to "{root}/folder/album"...',
         'Uploading "{testdata}/SmugCLI_2.jpg" to "{root}/folder/album"...'])
    self._do('ls {root}/folder/album',
             ['SmugCLI_1.gif',
              'SmugCLI_1.jpg',
              'SmugCLI_1.png',
              'SmugCLI_2.jpg',
              'SmugCLI_1.JPG'])

    # Can automatically create album with `-p`.
    self._do(
        'upload -p {testdata}/SmugCLI_1.jpg {root}/new_folder/new_album',
        ['Creating Folder "{root}/new_folder".',
         'Creating Album "{root}/new_folder/new_album".',
         'Uploading "{testdata}/SmugCLI_1.jpg" to '
         '"{root}/new_folder/new_album"...'])
    self._do('ls {root}/new_folder/new_album', ['SmugCLI_1.jpg'])

    # Gracefully aborts if trying to create a child of a file node.
    self._do(
        'upload -p {testdata}/SmugCLI_2.jpg '
        '{root}/folder/album/SmugCLI_1.jpg/foo',
        ['"/{root}/folder/album/SmugCLI_1.jpg" is a file, it can\'t have '
         'child nodes.'])

  def test_sync(self):
    """Test for `smugcli sync`."""
    self._stage_files('{root}/dir', ['{testdata}/SmugCLI_1.jpg',
                                     '{testdata}/SmugCLI_2.jpg',
                                     '{testdata}/SmugCLI_3.jpg'])
    self._stage_files('{root}/dir/album', ['{testdata}/SmugCLI_4.jpg',
                                           '{testdata}/SmugCLI_5.jpg'])
    self._do('sync {root} /',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)?',
              expect.Reply('yes'),
              expect.AnyOrder(
                  expect.Anything().repeatedly(),
                  'Creating folder "{root}".',
                  'Creating folder "{root}/dir".',
                  'Creating album "{root}/dir/Images from folder dir".',
                  'Creating album "{root}/dir/album".',
                  'Uploaded "{root}/dir/SmugCLI_1.jpg".',
                  'Uploaded "{root}/dir/SmugCLI_2.jpg".',
                  'Uploaded "{root}/dir/SmugCLI_3.jpg".',
                  'Uploaded "{root}/dir/album/SmugCLI_4.jpg".',
                  'Uploaded "{root}/dir/album/SmugCLI_5.jpg".')])

    self._do(
        'sync {root} /',
        ['Syncing "{root}" to SmugMug folder "/".',
         'Proceed (yes\\/no)?',
         expect.Reply('yes'),
         expect.AnyOrder(
             expect.Anything().repeatedly(),
             'Found matching remote album "{root}/dir/Images from folder dir".',
             'Found matching remote album "{root}/dir/album".')])

    with self._set_cwd(self._format_path('{root}')):
      self._do(
          'sync dir {root}',
          ['Syncing "dir" to SmugMug folder "/{root}".',
           'Proceed (yes\\/no)?',
           expect.Reply('yes'),
           expect.AnyOrder(
               expect.Anything().repeatedly(),
               'Found matching remote album '
               '"{root}/dir/Images from folder dir".',
               'Found matching remote album "{root}/dir/album".')])

    self._stage_files('{root}/dir',
                      [('{testdata}/SmugCLI_5.jpg', 'SmugCLI_2.jpg')])
    self._stage_files('{root}/dir/album',
                      [('{testdata}/SmugCLI_2.jpg', 'SmugCLI_5.jpg')])
    self._do(
        'sync {root} /',
        ['Syncing "{root}" to SmugMug folder "/".',
         'Proceed (yes\\/no)?',
         expect.Reply('yes'),
         expect.AnyOrder(
             expect.Anything().repeatedly(),
             'Found matching remote album "{root}/dir/Images from folder dir".',
             'File "{root}/dir/SmugCLI_2.jpg" exists, but has changed.'
             ' Deleting old version.',
             'Re-uploaded "{root}/dir/SmugCLI_2.jpg".',
             'Found matching remote album "{root}/dir/album".',
             'File "{root}/dir/album/SmugCLI_5.jpg" exists, but has changed.'
             ' Deleting old version.',
             'Re-uploaded "{root}/dir/album/SmugCLI_5.jpg".')])

  def test_sync_heic(self):
    """Test `smugcli sync` for HEIC files."""
    self._stage_files('{root}/album',
                      [('{testdata}/SmugCLI_1.heic', 'SmugCLI_1.heic'),
                       ('{testdata}/SmugCLI_1.heic', 'SmugCLI_2.HEIC')])
    self._do('sync {root} /',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)?',
              expect.Reply('yes'),
              expect.AnyOrder(
                  expect.Anything().repeatedly(),
                  'Creating folder "{root}".',
                  'Creating album "{root}/album".',
                  'Uploaded "{root}/album/SmugCLI_1.heic".',
                  'Uploaded "{root}/album/SmugCLI_2.HEIC".')])

    self._stage_files('{root}/album', [
        # Modify SmugCLI_1.heic
        ('{testdata}/SmugCLI_2.heic', 'SmugCLI_1.heic'),
        # Add a new HEIC file.
        ('{testdata}/SmugCLI_1.heic', 'SmugCLI_3.hEiC')])

    self._do(
        'sync {root} /',
        ['Syncing "{root}" to SmugMug folder "/".',
         'Proceed (yes\\/no)?',
         expect.Reply('yes'),
         expect.AnyOrder(
             'Found matching remote album "{root}/album".',
             'Uploaded "{root}/album/SmugCLI_3.hEiC".',
             # Even though SmugCLI_1.heic changed, there is no way to detect
             # this because SmugMug doesn't keep HEIC image metadata. Hence,
             # HEIC files are considered immutable and are never re-uploaded.
             expect.Not(expect.Or(
                 'Uploaded "{root}/album/SmugCLI_1.heic".',
                 'Uploaded "{root}/album/SmugCLI_2.HEIC".')).repeatedly())])

  def test_sync_privacy(self):
    """Test the `--privacy` option of `smugcli sync`."""
    self._stage_files('{root}/default/album', ['{testdata}/SmugCLI_1.jpg'])
    self._do('sync {root}',
             expect.Somewhere(expect.Reply('yes')))
    self._do('ls -l {root}/default',
             expect.Somewhere('"Privacy": "Public",'))

    self._stage_files('{root}/public/album', ['{testdata}/SmugCLI_1.jpg'])
    self._do('sync {root} --privacy=public',
             expect.Somewhere(expect.Reply('yes')))
    self._do('ls -l {root}/public',
             expect.Somewhere('"Privacy": "Public",'))

    self._stage_files('{root}/unlisted/album', ['{testdata}/SmugCLI_1.jpg'])
    self._do('sync {root} --privacy=unlisted',
             expect.Somewhere(expect.Reply('yes')))
    self._do('ls -l {root}/unlisted',
             expect.Somewhere('"Privacy": "Unlisted",'))

    self._stage_files('{root}/private/album', ['{testdata}/SmugCLI_1.jpg'])
    self._do('sync {root} --privacy=private',
             expect.Somewhere(expect.Reply('yes')))
    self._do('ls -l {root}/private',
             expect.Somewhere('"Privacy": "Private",'))

  def test_sync_folder_depth_limits(self):
    """Test SmugMug's folder nesting limit when using `smugcli sync`."""
    self._stage_files('{root}/1/2/3/4/album', ['{testdata}/SmugCLI_1.jpg'])
    self._do(
        'sync {root}',
        ['Syncing "{root}" to SmugMug folder "/".',
         'Proceed (yes\\/no)?',
         expect.Reply('yes'),
         expect.AnyOrder(
             expect.Anything().repeatedly(),
             'Creating folder "{root}".',
             'Creating folder "{root}/1".',
             'Creating folder "{root}/1/2".',
             'Creating folder "{root}/1/2/3".',
             'Creating folder "{root}/1/2/3/4".',
             'Creating album "{root}/1/2/3/4/album".',
             'Uploaded "{root}/1/2/3/4/album/SmugCLI_1.jpg".')])

    with self._set_cwd(self._format_path('{root}/1')):
      self._do('sync 2 {root}/1',
               ['Syncing "2" to SmugMug folder "/{root}/1".',
                'Proceed (yes\\/no)?',
                expect.Reply('yes'),
                expect.AnyOrder(
                    expect.Anything().repeatedly(),
                    'Found matching remote album "{root}/1/2/3/4/album".')])

    self._stage_files('{root}/1/2/3/4/5/album', ['{testdata}/SmugCLI_1.jpg'])
    self._do('sync {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)?',
              expect.Reply('yes'),
              expect.AnyOrder(
                  expect.Anything().repeatedly(),
                  'Cannot create "{root}/1/2/3/4/5/album", SmugMug does not'
                  ' support folder more than 5 level deep.')])

    with self._set_cwd(self._format_path('{root}/1')):
      self._do('sync 2 {root}/1',
               ['Syncing "2" to SmugMug folder "/{root}/1".',
                'Proceed (yes\\/no)?',
                expect.Reply('yes'),
                expect.AnyOrder(
                    expect.Anything().repeatedly(),
                    'Cannot create "{root}/1/2/3/4/5/album", SmugMug does not'
                    ' support folder more than 5 level deep.')])

  def test_sync_whitespace(self):
    """Test `smugcli sync` when files or folders contain white spaces."""
    if os.name == 'nt':
      folder = '{root}/ folder/ album'
      filename = ' file . jpg'
    else:
      folder = '{root}/ folder / album '
      filename = ' file . jpg '

    self._stage_files(folder, [('{testdata}/SmugCLI_1.jpg', filename)])
    self._do('sync {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)?',
              expect.Reply('yes'),
              expect.AnyOrder(
                  expect.Anything().repeatedly(),
                  'Creating folder "{root}".',
                  'Creating folder "{root}/folder".',
                  'Creating album "{root}/folder/album".',
                  f'Uploaded "{folder}/{filename}".')])
    self._do('sync {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)?',
              expect.Reply('yes'),
              expect.AnyOrder(
                  expect.Anything().repeatedly(),
                  'Found matching remote album "{root}/folder/album".')])

  def test_sync_confirmation(self):
    """Test the different ways `smugcli sync` operation can be confirmed."""
    self._stage_files('{root}/album', ['{testdata}/SmugCLI_1.jpg'])
    self._do('sync {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)? ',
              expect.Reply('yes'),
              expect.AnyOrder(
                  expect.Anything().repeatedly(),
                  'Creating folder "{root}".',
                  'Creating album "{root}/album".',
                  'Uploaded "{root}/album/SmugCLI_1.jpg".')])

    self._do('sync {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)? ',
              expect.Reply('y'),
              expect.AnyOrder(
                  expect.Anything().repeatedly(),
                  'Found matching remote album "{root}/album".')])

    self._do('sync {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)? ',
              expect.Reply('no')])

    self._do('sync {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)? ',
              expect.Reply('n')])

  def test_sync_force(self):
    """Test the `--force` option of `smugcli sync`."""
    self._stage_files('{root}/album', ['{testdata}/SmugCLI_1.jpg'])
    self._do('sync -f {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              expect.AnyOrder(
                  expect.Anything().repeatedly(),
                  'Creating folder "{root}".',
                  'Creating album "{root}/album".',
                  'Uploaded "{root}/album/SmugCLI_1.jpg".')])

    self._do('sync --force {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              expect.AnyOrder(
                  expect.Anything().repeatedly(),
                  'Found matching remote album "{root}/album".')])

  def test_sync_in_place(self):
    """Test the `--in_place` option of `smugcli sync`."""
    self._stage_files('{root}/album', ['{testdata}/SmugCLI_1.jpg'])
    self._do('sync {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)?',
              expect.Reply('yes'),
              expect.AnyOrder(
                  expect.Anything().repeatedly(),
                  'Creating folder "{root}".',
                  'Creating album "{root}/album".',
                  'Uploaded "{root}/album/SmugCLI_1.jpg".')])

    web_uri = self._do('ls -l -q WebUri {root}/album/SmugCLI_1.jpg')

    self._stage_files(
        '{root}/album/SmugCLI_1.jpg', ['{testdata}/SmugCLI_2.jpg'])
    self._do('sync --in_place {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)?',
              expect.Reply('yes'),
              expect.AnyOrder(
                  expect.Anything().repeatedly(),
                  'Found matching remote album "{root}/album".',
                  'File "{root}/album/SmugCLI_1.jpg" exists, but has changed.'
                  ' Upload in place.',
                  'Re-uploaded "{root}/album/SmugCLI_1.jpg".')])

    self._do('ls -l -q WebUri {root}/album/SmugCLI_1.jpg',
             expect.Url(expect.Equals(web_uri)))

    self._stage_files(
        '{root}/album/SmugCLI_1.jpg', ['{testdata}/SmugCLI_3.jpg'])
    self._do('sync {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)?',
              expect.Reply('yes'),
              expect.AnyOrder(
                  expect.Anything().repeatedly(),
                  'Found matching remote album "{root}/album".',
                  'File "{root}/album/SmugCLI_1.jpg" exists, but has changed.'
                  ' Deleting old version.',
                  'Re-uploaded "{root}/album/SmugCLI_1.jpg".')])

    self._do('ls -l -q WebUri {root}/album/SmugCLI_1.jpg',
             expect.Url(expect.Not(expect.Equals(web_uri))))

  def test_sync_sub_folders(self):
    """Test syncing to sub-folders."""
    self._stage_files('{root}/local/album', ['{testdata}/SmugCLI_1.jpg'])
    self._do('mkdir -p {root}/Pics')
    self._do('sync {root}/local/album {root}/Pics',
             ['Syncing "{root}/local/album" to SmugMug folder "/{root}/Pics".',
              'Proceed (yes\\/no)? ',
              expect.Reply('y'),
              expect.AnyOrder(
                  expect.Anything().repeatedly(),
                  'Creating album "{root}/Pics/album".',
                  'Uploaded "{root}/local/album/SmugCLI_1.jpg".')])

    self._do('sync {root}/local/album/ {root}/Pics/album',
             ['Syncing "{root}/local/album/" to SmugMug album '
              '"/{root}/Pics/album".',
              'Proceed (yes\\/no)? ',
              expect.Reply('y'),
              expect.AnyOrder(
                  expect.Anything().repeatedly(),
                  'Found matching remote album "{root}/Pics/album".')])

  def test_sync_invalid_src(self):
    """Test invalid source file handling for `smugcli sync`."""
    self._stage_files('{root}/album', ['{testdata}/SmugCLI_1.jpg'])
    self._do('mkalbum -p {root}')

    self._do('sync {root}/file {root}/folder/ {root}/dir/* {root}',
             ['Files not found:',
              '{root}/file',
              '{root}/folder/',
              '{root}/dir/*'])

    self._do('sync {root}/file {root}/album/ {root}/dir/* {root}',
             ['Files not found:',
              '{root}/file',
              '{root}/dir/*'])

    self._do('sync {root}/file {root}',
             ['File not found:',
              '{root}/file'])

    self._do('sync {root}/album/* {root}',
             ['Syncing "{root}/album/SmugCLI_1.jpg" to SmugMug album '
              '"/{root}".',
              'Proceed (yes\\/no)?',
              expect.Reply('no')])

  def test_sync_folder(self):
    """Test `smugcli sync` for folder source."""
    self._stage_files('{root}/src/album1', ['{testdata}/SmugCLI_1.jpg',
                                            '{testdata}/SmugCLI_2.jpg'])
    self._stage_files('{root}/src/album2', ['{testdata}/SmugCLI_3.jpg'])
    self._do('mkdir -p {root}/dst')

    self._do('sync {root}/src/ {root}/dst',
             ['Syncing "{root}/src/" to SmugMug folder "/{root}/dst"',
              'Proceed (yes\\/no)?',
              expect.Reply('yes'),
              expect.AnyOrder(
                  expect.Anything().repeatedly(),
                  'Creating album "{root}/dst/album1".',
                  'Uploaded "{root}/src/album1/SmugCLI_1.jpg".',
                  'Uploaded "{root}/src/album1/SmugCLI_2.jpg".',
                  'Creating album "{root}/dst/album2".',
                  'Uploaded "{root}/src/album2/SmugCLI_3.jpg".')])

  def test_sync_multiple_files(self):
    """Test `smugcli sync` with multiple input files."""
    self._stage_files('{root}/dir1', ['{testdata}/SmugCLI_1.jpg'])
    self._stage_files('{root}/dir2', ['{testdata}/SmugCLI_1.jpg',
                                      '{testdata}/SmugCLI_2.jpg',
                                      '{testdata}/SmugCLI_3.jpg'])
    self._stage_files('{root}/dir3', ['{testdata}/SmugCLI_1.jpg'])
    self._do('mkalbum -p {root}/album')

    self._do('sync {root}/dir1/*.jpg {root}/dir2/* {root}/dir3/ {root}/album',
             ['Syncing:',
              '  {root}/dir1/SmugCLI_1.jpg',
              '  {root}/dir2/SmugCLI_1.jpg',
              '  {root}/dir2/SmugCLI_2.jpg',
              '  {root}/dir2/SmugCLI_3.jpg',
              '  {root}/dir3/',
              'to SmugMug album "/{root}/album"',
              'Proceed (yes\\/no)?',
              expect.Reply('yes'),
              expect.AnyOrder(
                  expect.Anything().repeatedly(),
                  'Found matching remote album "{root}/album".',
                  'Uploaded "{root}/dir1/SmugCLI_1.jpg".',
                  'Uploaded "{root}/dir2/SmugCLI_1.jpg".',
                  'Uploaded "{root}/dir2/SmugCLI_2.jpg".',
                  'Uploaded "{root}/dir2/SmugCLI_3.jpg".',
                  'Uploaded "{root}/dir3/SmugCLI_1.jpg".',
                  'Sync complete.')])

  def test_sync_multiple_folders(self):
    """Test `smugcli sync` for multiple input folders."""
    self._stage_files('{root}/album1', ['{testdata}/SmugCLI_1.jpg'])
    self._stage_files('{root}/dir2/album2', ['{testdata}/SmugCLI_2.jpg'])
    self._stage_files('{root}/dir3/subdir3/album3',
                      ['{testdata}/SmugCLI_3.jpg'])
    self._do('mkdir -p {root}/folder')

    self._do('sync {root}/album1 {root}/dir2/* {root}/dir3/ {root}/folder',
             ['Syncing:',
              '  {root}/album1',
              '  {root}/dir2/album2',
              '  {root}/dir3/',
              'to SmugMug folder "/{root}/folder"',
              'Proceed (yes\\/no)?',
              expect.Reply('yes'),
              expect.AnyOrder(
                  expect.Anything().repeatedly(),
                  'Creating album "{root}/folder/album1".',
                  'Creating album "{root}/folder/album2".',
                  'Creating folder "{root}/folder/subdir3".',
                  'Creating album "{root}/folder/subdir3/album3".',
                  'Uploaded "{root}/album1/SmugCLI_1.jpg".',
                  'Uploaded "{root}/dir2/album2/SmugCLI_2.jpg".',
                  'Uploaded "{root}/dir3/subdir3/album3/SmugCLI_3.jpg".',
                  'Sync complete.')])

  def test_sync_paths_to_album(self):
    """Test `smugcli sync` for a list of source paths to an album node."""
    self._stage_files('{root}/dir1', ['{testdata}/SmugCLI_1.jpg',
                                      '{testdata}/SmugCLI_2.jpg'])
    self._do('mkalbum -p {root}/album')
    self._do('sync {root}/dir1/* {root}/album',
             ['Syncing:',
              '  {root}/dir1/SmugCLI_1.jpg',
              '  {root}/dir1/SmugCLI_2.jpg',
              'to SmugMug album "/{root}/album".',
              'Proceed (yes\\/no)?',
              expect.Reply('yes'),
              expect.AnyOrder(
                  expect.Anything().repeatedly(),
                  'Found matching remote album "{root}/album".',
                  'Uploaded "{root}/dir1/SmugCLI_1.jpg".',
                  'Uploaded "{root}/dir1/SmugCLI_2.jpg".')])

  def test_sync_files_to_album(self):
    """Test `smugcli sync` for a list of source files to an album node."""
    self._stage_files('{root}/dir1', ['{testdata}/SmugCLI_1.jpg',
                                      '{testdata}/SmugCLI_2.jpg'])
    self._do('mkalbum -p {root}/album')
    with self._set_cwd(self._format_path('{root}/dir1')):
      self._do('sync * {root}/album',
               ['Syncing:',
                '  SmugCLI_1.jpg',
                '  SmugCLI_2.jpg',
                'to SmugMug album "/{root}/album".',
                'Proceed (yes\\/no)?',
                expect.Reply('yes'),
                expect.AnyOrder(
                    expect.Anything().repeatedly(),
                    'Found matching remote album "{root}/album".',
                    'Uploaded "./SmugCLI_1.jpg".',
                    'Uploaded "./SmugCLI_2.jpg".')])

  def test_sync_files_to_folder(self):
    """Test that `smugcli sync` rejects syncing files to a folder node."""
    self._stage_files('{root}', ['{testdata}/SmugCLI_1.jpg',
                                 '{testdata}/SmugCLI_2.jpg'])
    self._do('mkdir -p {root}/folder')
    self._do('sync {root}/* {root}/folder',
             'Can\'t upload files to folder. Please sync to an album node.')

  def test_sync_folders_to_album(self):
    """Test that `smugcli sync` rejects syncing folder to an album node."""
    self._stage_files('{root}/dir1', ['{testdata}/SmugCLI_1.jpg'])
    self._stage_files('{root}/dir2', ['{testdata}/SmugCLI_2.jpg'])
    self._do('mkalbum -p {root}/album')
    self._do('sync {root}/* {root}/album',
             'Can\'t upload folders to an album. Please sync to a folder node.')

  def test_sync_to_file_node(self):
    """Test that `smugcli sync` rejects syncing to a target file node."""
    # Can't sync to a file.
    self._stage_files('{root}/album', ['{testdata}/SmugCLI_1.jpg'])
    self._do('upload -p {root}/album/SmugCLI_1.jpg {root}/album')
    self._do('sync . {root}/album/SmugCLI_1.jpg',
             'Can\'t sync to a file node.')

    # File nodes can't have child nodes.
    self._do(
        'sync . {root}/album/SmugCLI_1.jpg/foo',
        '"/{root}/album/SmugCLI_1.jpg" is a file, it can\'t have child nodes.')

  def test_sync_default_arguments(self):
    """Test default arguments for `smugcli sync`."""
    self._stage_files('{root}', ['{testdata}/SmugCLI_1.jpg',
                                 '{testdata}/SmugCLI_2.jpg',
                                 '{testdata}/SmugCLI_3.jpg'])
    self._do('mkalbum -p {root}')
    self._do('sync',
             ['Syncing "." to SmugMug folder "/".',
              'Proceed (yes\\/no)?',
              expect.Reply('no')])

    self._do('sync {root}',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)?',
              expect.Reply('no')])

    self._do('sync {root}/ {root}',
             ['Syncing "{root}/" to SmugMug album "/{root}".',
              'Proceed (yes\\/no)?',
              expect.Reply('no')])

    self._do('sync {root}/SmugCLI_1.jpg {root}/SmugCLI_2.jpg {root}',
             ['Syncing:',
              '  {root}/SmugCLI_1.jpg',
              '  {root}/SmugCLI_2.jpg',
              'to SmugMug album "/{root}".',
              'Proceed (yes\\/no)?',
              expect.Reply('no')])

  def test_sync_deprecated_target_argument(self):
    """Test handling of deprecated `smugcli sync --target`."""
    self._do('sync -t dst',
             ['-t\\/--target argument no longer exists.',
              'Specify the target folder as the last positional argument.'])

    self._do('sync --target=dst',
             ['-t\\/--target argument no longer exists.',
              'Specify the target folder as the last positional argument.'])

    self._do('sync a -t dst',
             ['-t\\/--target argument no longer exists.',
              'Specify the target folder as the last positional argument.'])

    self._do('sync a --target=dst',
             ['-t\\/--target argument no longer exists.',
              'Specify the target folder as the last positional argument.'])

    self._do('sync a b -t dst',
             ['-t\\/--target argument no longer exists.',
              'Specify the target folder as the last positional argument.'])

    self._do('sync a b --target=dst',
             ['-t\\/--target argument no longer exists.',
              'Specify the target folder as the last positional argument.'])

  def test_ignore_include(self):
    """Test for `smugcli ignore` and `smugcli include`."""
    self._stage_files('{root}/album1', ['{testdata}/SmugCLI_1.jpg',
                                        '{testdata}/SmugCLI_2.jpg',
                                        '{testdata}/SmugCLI_3.jpg'])
    self._stage_files('{root}/album2', ['{testdata}/SmugCLI_4.jpg',
                                        '{testdata}/SmugCLI_5.jpg'])
    self._do('ignore {root}/album1/SmugCLI_2.jpg {root}/album2', [])
    self._do('sync {root} /',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)?',
              expect.Reply('yes'),
              expect.AnyOrder(
                  expect.Not(expect.Or(
                      'Creating album "{root}/album2".',
                      'Uploaded "{root}/album1/SmugCLI_2.jpg".',
                      'Uploaded "{root}/album2/SmugCLI_4.jpg".',
                      'Uploaded "{root}/album2/SmugCLI_5.jpg".')).repeatedly(),
                  'Creating folder "{root}".',
                  'Creating album "{root}/album1".',
                  'Uploaded "{root}/album1/SmugCLI_1.jpg".',
                  'Uploaded "{root}/album1/SmugCLI_3.jpg".',
                  'Sync complete.')])

    self._do('include {root}/album1/SmugCLI_2.jpg {root}/album2', [])
    self._do('sync {root} /',
             ['Syncing "{root}" to SmugMug folder "/".',
              'Proceed (yes\\/no)?',
              expect.Reply('yes'),
              expect.AnyOrder(
                  expect.Anything().repeatedly(),
                  'Found matching remote album "{root}/album1".',
                  'Creating album "{root}/album2".',
                  'Uploaded "{root}/album1/SmugCLI_2.jpg".',
                  'Uploaded "{root}/album2/SmugCLI_4.jpg".',
                  'Uploaded "{root}/album2/SmugCLI_5.jpg".',
                  'Sync complete.')])


if __name__ == '__main__':
  unittest.main()
