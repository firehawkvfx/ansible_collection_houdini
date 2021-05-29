# execute example 
# python houdini_install.py -u 'mysesiusername' -p 'mysesipass' -i '/opt/houdini' -b 'daily'

import sys, re, os, shutil, argparse
import getpass
try:
    import requests
except ImportError:
    print 'This script require requests module.\n Install: pip install requests'
    sys.exit(1)
try:
    from bs4 import BeautifulSoup
except ImportError:
    print 'This scrip require BeautifulSoup package (https://www.crummy.com/software/BeautifulSoup/bs4/doc/#).' \
          '\nInstall: pip install beautifulsoup4'
    sys.exit(1)

# VARIABLES ################################
parser = argparse.ArgumentParser()
parser.add_argument("-i", "--install_dir", type=str, help="Installation dir")
parser.add_argument("-t", "--temp_download_dir", type=str, help="Temp Download dir")
parser.add_argument("-u", "--username", type=str, help="SideFx account username")
parser.add_argument("-p", "--password", type=str, help="SideFx account password")
parser.add_argument("-s", "--server", type=str, help="Install License server (y/yes, n/no, a/auto, default auto)")
parser.add_argument("-b", "--buildtype", type=str, help="Use latest daily build (d/daily, p/production)")
parser.add_argument("-f", "--filename", type=str, help="Use a specific file to install houdini (houdini-17.5.326-linux_x86_64_gcc6.3.tar.gz)")
parser.add_argument("-d", "--downloadonly", type=str, help="Download latest installer only without install (true)")
parser.add_argument("-q", "--queryonly", type=str, help="query the filename only for the latest daily or produciton build (true)")
# parser.add_argument("-hq", "--hqserver", type=str, help="Install HQ server (y/yes, n/no, a/auto, default auto)")

_args, other_args = parser.parse_known_args()
username = _args.username
password = _args.password

if not username or not password:
    print 'Please set username and password'
    print 'Example: -u username -p password'
    sys.exit(1)

install_dir = _args.install_dir
if not install_dir:
    print 'ERROR: Please set installation folder in argument -i. For example: -i "%s"' % ('/opt/houdini' if os.name == 'postx' else 'c:\\cg\\houdini')
    sys.exit(1)
install_dir = install_dir.replace('\\', '/').rstrip('/')

tmp_folder = _args.temp_download_dir
if tmp_folder:
    tmp_folder = os.path.expanduser(_args.temp_download_dir)
else:
    tmp_folder = os.path.expanduser('/var/tmp/firehawk')
tmp_folder = tmp_folder.replace('\\', '/').rstrip('/')

# license server
lic_server = False
if os.name == 'nt':
    if not os.path.exists('C:/Windows/System32/sesinetd.exe'):
        lic_server = True
elif os.name == 'posix':
    if not os.path.exists('/usr/lib/sesi/sesinetd'):
        lic_server = True

if _args.server:
    if _args.server in ['y', 'yes']:
        lic_server = True
    elif _args.server in ['n', 'no']:
        lic_server = False

buildtype = "production"
downloadonly = False

if _args.downloadonly:
    if _args.downloadonly in ['true']:
        print "will download latest without install"
        downloadonly = True

queryonly = False
if _args.queryonly:
    if _args.queryonly in ['true']:
        print "will query latest filename without download or install"
        queryonly = True

if _args.buildtype:
    if _args.buildtype in ['d', 'daily']:
        print "get daily build"
        buildtype = "daily"
    elif _args.buildtype in ['p', 'production']:
        print "get production build"
        buildtype = "production"

existing_filename = None
if _args.filename and _args.filename != 'auto':
    existing_filename = os.path.join(tmp_folder, _args.filename).replace('\\', '/')
    print "existing_filename", existing_filename

# hq server
# hq_server = False
# if os.name == 'nt':
#     if not os.path.exists('C:/Windows/System32/sesinetd.exe'):
#         lic_server = True
# elif os.name == 'posix':
#     if not os.path.exists(''):
#         lic_server = True


############################################################# START #############


def create_output_dir(install_dir, build):
    """
    Change this to define installation folder
    """
    if os.name == 'nt':
        return os.path.join(install_dir, build).replace('/', '\\')
    else:
        return '/'.join([install_dir.rstrip('/'), build])


def windows_is_admin():
    import ctypes
    try:
        is_admin = os.getuid() == 0
    except AttributeError:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    return is_admin


# define OS
if os.name == 'nt':
    category = 'win'
    if not windows_is_admin():
        print 'Run this script as administrator'
        sys.exit(1)
elif os.name == 'posix':
    category = 'linux'
else:
    raise Exception('This OS not supported')

# create client
client = requests.session()
# Retrieve the CSRF token first
URL = 'https://www.sidefx.com/login/'
print 'Login on %s ...' % URL
client.get(URL)  # sets cookie
csrftoken = client.cookies['csrftoken']
# create login data
login_data = dict(username=username, password=password, csrfmiddlewaretoken=csrftoken, next='/')
# login
r = client.post(URL, data=login_data, headers=dict(Referer=URL))

if ('daily' in buildtype):
    print 'Get last daily build version...'
    pageurl = "https://www.sidefx.com/download/daily-builds/#category-devel"
    page = client.get(pageurl)

    s = BeautifulSoup(page.content, 'html.parser')
    # get last daily build
    a = s.find('div', {'class': lambda x: x and 'category-'+category in x.split() and 'category-devel' in x.split()}).find('a')
else:
    print 'Get last production build version...'
    pageurl = "https://www.sidefx.com/download/daily-builds/#category-gold"
    page = client.get(pageurl)

    s = BeautifulSoup(page.content, 'html.parser')
    # get last version
    a = s.find('div', {'class': lambda x: x and 'category-'+category in x.split()}).find('a')

# get build
build = re.match(r".*?(\d+\.\d+\.\d+).*", str(a.text)).group(1)

if existing_filename is not None:
    build = re.match(r".*?(\d+\.\d+\.\d+).*", str(_args.filename)).group(1)

print 'Last build is ', build

def get_recursive_size(path):
    size = sum( os.path.getsize(os.path.join(dirpath,filename)) for dirpath, dirnames, filenames in os.walk( path ) for filename in filenames )
    return size

import math

def convert_size(size_bytes):
   if size_bytes == 0:
       return "0B"
   size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
   i = int(math.floor(math.log(size_bytes, 1024)))
   p = math.pow(1024, i)
   s = round(size_bytes / p, 2)
   return "%s %s" % (s, size_name[i])

# check your last version here
if not os.path.exists(install_dir):
    os.makedirs(install_dir)

if queryonly:
    print "File:", a.text
else:
    # note, this isn't thourough enough.  the check should probably be handled in ansible.
    list_dir = os.listdir(install_dir)
    folder_size = get_recursive_size(os.path.join(install_dir, build))
    # if installed size is < 100MB approx, then overwrite.
    min_size = 100000000
    if build in list_dir and folder_size > 1000000:
        print 'Existing Dirs:', list_dir, 'In:', install_dir
        print 'Build {} already installed'.format(build)
        print 'Folder Size:', convert_size(folder_size)
        sys.exit(1)
    
    # create local file path
    if not os.path.exists(tmp_folder):
        os.makedirs(tmp_folder)

    
    need_to_download = True
    if existing_filename is not None:
        need_to_download = False
        local_filename = existing_filename
        print '  Existing File Specified, Changed to:', existing_filename
    else:
        # if your version is lower go to download
        print 'Start download...'
        # download url
        url = 'http://www.sidefx.com' + a.get('href').split('=')[-1] + 'get/'
        print '  DOWNLOAD URL:', url
        local_filename = os.path.join(tmp_folder, a.text).replace('\\', '/')
        
        # get content
        resp = client.get(url, stream=True)
        total_length = int(resp.headers.get('content-length'))
        
        if os.path.exists(local_filename):
            # compare file size to see if file should be downloaded
            local_size = os.path.getsize(local_filename)
            print "local size", local_size, "download size", total_length
            if not local_size == total_length:
                os.remove(local_filename)
                print "size not equal"
            else:
                # skip downloading if file already exists
                print 'Skip download, File already Present', local_filename
                need_to_download = False
    
    print '  Local File:', local_filename
    if need_to_download:
        # download file
        print 'Total size %sMb' % int(total_length/1024.0/1024.0)
        block_size = 1024*4*16*16
        dl = 0
        with open(local_filename, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=block_size):
                if chunk:
                    f.write(chunk)
                    f.flush()
                    dl += len(chunk)
                    done = int(50 * dl / total_length)
                    sys.stdout.write("\r[%s%s] %sMb of %sMb" % ('=' * done,
                                                                ' ' * (50-done),
                                                                int(dl/1024.0/1024.0),
                                                                int(total_length/1024.0/1024.0)
                                                                )
                                    )
                    sys.stdout.flush()
        print
        print 'Download complete'

    if downloadonly == True:
        print "Skipping installation.  Download Only:", local_filename
    else:
        # start silent installation
        print 'Start install Houdini'
        if os.name == 'posix':
            # unzip
            print 'Unpack "%s" to "%s"' % (local_filename, tmp_folder)
            cmd = 'sudo tar xf {} -C {}'.format(local_filename, tmp_folder)
            os.system(cmd)
            # os.remove(local_filename)
            install_file = os.path.join(tmp_folder, os.path.splitext(os.path.splitext(os.path.basename(local_filename))[0])[0], 'houdini.install')
            print 'Install File', install_file
            # ./houdini.install --auto-install --accept-EULA 2020-05-05 --make-dir /opt/houdini/16.0.705
            out_dir = create_output_dir(install_dir, build)
            flags = '--auto-install --accept-EULA 2020-05-05 --install-houdini --no-license --install-hfs-symlink --make-dir'
            if lic_server:
                pass
            cmd = 'sudo ./houdini.install {flags} {dir}'.format(
                flags=flags,
                dir=out_dir
            )
            print 'Create output folder', out_dir
            if not os.path.exists(out_dir):
                print 'Create folder:', out_dir
                os.makedirs(out_dir)
            print 'Start install...', install_file
            # print 'CMD:\n'+cmd
            print 'GoTo', os.path.dirname(install_file)
            os.chdir(os.path.dirname(install_file))
            print "use install file", install_file
            print 'CMD:\n' + cmd
            os.system(cmd)
            # sudo chown -R paul: /opt/houdini/16.0.705
            # sudo chmod 777 -R
            # whoami
            # setup permission
            os.system('chown -R %s: %s' % (getpass.getuser(), out_dir))
            os.system('chmod 777 -R ' + out_dir)
            # delete downloaded file
            # shutil.rmtree(tmp_folder)
        else:
            out_dir = create_output_dir(install_dir, build)
            print 'Create output folder', out_dir
            if not os.path.exists(out_dir):
                os.makedirs(out_dir)
            cmd = '"{houdini_install}" /S /AcceptEula=yes /LicenseServer={lic_server} /DesktopIcon=No ' \
                '/FileAssociations=Yes /HoudiniServer=No /EngineUnity=No ' \
                '/EngineMaya=No /EngineUnreal=No /HQueueServer=No ' \
                '/HQueueClient=No /IndustryFileAssociations=Yes /InstallDir="{install_dir}" ' \
                '/ForceLicenseServer={lic_server} /MainApp=Yes /Registry=Yes'.format(
                    lic_server='Yes' if lic_server else 'No',
                    houdini_install=local_filename,
                    install_dir=out_dir
                    )
            print 'CMD:\n' + cmd
            print 'Start install...'
            os.system(cmd)
            print 'If installation not happen, repeat process.'
