#!/usr/bin/env python

import traceback
import os
import zipfile
import tarfile
import shutil
import subprocess

from . import plat

__ = plat.__

##############################################################################


def run(interface, *args, **kwargs):
    """
    Runs the supplied arguments.
    """

    try:
        interface.call(args, **kwargs)
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def run_slow(interface, *args, **kwargs):
    """
    Runs the supplied arguments in a manner that lets the program
    be cancelled.
    """

    try:
        interface.call(args, cancel=True, **kwargs)
    except (subprocess.CalledProcessError, OSError):
        return False
    return True


##############################################################################
def check_java(interface):
    """
    Checks for the presence of a minimally useful java on the user's system.
    """

    interface.info(__("I'm compiling a short test program, to see if you have a working JDK on your system."))

    if not run_slow(interface, plat.javac, plat.path("buildlib/CheckJDK8.java"), use_path=True):
        interface.fail(__("I was unable to use javac to compile a test file. If you haven't installed the Java Development Kit yet, please download it from:\n\nhttps://adoptopenjdk.net/?variant=openjdk8&jvmVariant=hotspot\n\nThe JDK is different from the JRE, so it's possible you have Java without having the JDK. Without a working JDK, I can't continue."))

    if not run_slow(interface, plat.java, "-classpath", plat.path("buildlib"), "CheckJDK8", use_path=True):
        interface.fail(__("The version of Java on your computer does not appear to be JDK 8, which is the only version supported by the Android SDK. If you need to install JDK 8, you can download it from:\n\nhttps://adoptopenjdk.net/?variant=openjdk8&jvmVariant=hotspot\n\nYou can also set the JAVA_HOME environment variable to use a different version of Java."))

    interface.success(__("The JDK is present and working. Good!"))


class FixedZipFile(zipfile.ZipFile):
    """
    Patches zipfile.zipfile so it sets the executable bit when necessary.
    """

    def extract(self, member, path=None, pwd=None):

        if not isinstance(member, zipfile.ZipInfo):
            member = self.getinfo(member)

        if path is None:
            path = os.getcwd()

        ret_val = self._extract_member(member, path, pwd)
        attr = member.external_attr >> 16

        if attr:
            os.chmod(ret_val, attr)

        return ret_val


def unpack_sdk(interface):

    if os.path.exists(plat.sdkmanager):
        interface.success(__("The Android SDK has already been unpacked."))
        return

    if "RAPT_NO_TERMS" not in os.environ:
        interface.terms("https://developer.android.com/studio/terms", __("Do you accept the Android SDK Terms and Conditions?"))

    if plat.windows:
        archive = "commandlinetools-windows-{}.zip".format(plat.sdk_version)
    elif plat.macintosh:
        archive = "commandlinetools-darwin-{}.zip".format(plat.sdk_version)
    elif plat.linux:
        archive = "commandlinetools-linux-{}.zip".format(plat.sdk_version)

    url = "https://dl.google.com/android/repository/" + archive

    interface.info(__("I'm downloading the Android SDK. This might take a while."))

    interface.download(url, plat.path(archive))

    interface.info(__("I'm extracting the Android SDK."))

    def extract():

        zf = FixedZipFile(plat.path(archive))

        # We have to do this because Python has a small (260?) path length
        # limit on windows, and the Android SDK has very long filenames.
        old_cwd = os.getcwd()
        os.chdir(plat.path("."))

        zf.extractall("Sdk")

        zf.close()

        # sdkmanager won't run unless we reorganize the unpack.
        os.rename("Sdk/cmdline-tools", "Sdk/latest")
        os.mkdir("Sdk/cmdline-tools")
        os.rename("Sdk/latest", "Sdk/cmdline-tools/latest")

        os.chdir(old_cwd)

    interface.background(extract)

    interface.success(__("I've finished unpacking the Android SDK."))


def get_packages(interface):

    packages = [ ]

    wanted_packages = [
        ("platform-tools", "platform-tools"),
        ("platforms;android-30", "platforms/android-30"),
        ]

    for i, j in wanted_packages:
        if not os.path.exists(os.path.join(plat.sdk, j)):
            packages.append(i)

    if packages:

        interface.info(__("I'm about to download and install the required Android packages. This might take a while."))

        if not run_slow(interface, plat.sdkmanager, "--update", yes=True):
            interface.fail(__("I was unable to accept the Android licenses."))

        if not run_slow(interface, plat.sdkmanager, "--licenses", yes=True):
            interface.fail(__("I was unable to accept the Android licenses."))

        if not run_slow(interface, plat.sdkmanager, yes=True, *packages):
            interface.fail(__("I was unable to install the required Android packages."))

    interface.success(__("I've finished installing the required Android packages."))


local_properties = plat.path("project/local.properties")
bundle_properties = plat.path("project/bundle.properties")


def set_property(properties, key, value, replace=False):
    """
    Sets the property `key` in local/bundle.properties to `value`. If replace is True,
    replaces the value.
    """

    lines = [ ]

    try:
        with open(properties, "r") as f:
            for l in f:
                k = l.partition("=")[0].strip()

                if k == key:
                    if not replace:
                        return
                    else:
                        continue

                lines.append(l)

    except:
        pass

    with open(properties, "w") as f:
        for l in lines:
            f.write(l)

        f.write("{}={}\n".format(key, value))


def get_property(properties, key):

    with open(properties, "r") as f:
        for l in f:
            k, _, v = l.partition("=")

            if k.strip() == key:
                return v.strip()

    return None


def get_local_key_properties():
    return [
        "--ks", get_property(local_properties, "key.store"),
        "--ks-pass", "pass:" + get_property(local_properties, "key.store.password"),
        "--ks-key-alias", get_property(local_properties, "key.alias"),
        "--key-pass", "pass:" + get_property(local_properties, "key.alias.password"),
    ]

def generate_keys(interface):

    properties = local_properties

    set_property(properties, "key.alias", "android")
    set_property(properties, "key.store.password", "android")
    set_property(properties, "key.alias.password", "android")

    default_keystore = plat.path("android.keystore").replace("\\", "/")

    set_property(properties, "key.store", default_keystore)

    if get_property(properties, "key.store") != default_keystore:
        interface.info(__("You set the keystore yourself, so I'll assume it's how you want it."))
        return

    if os.path.exists(plat.path("android.keystore")):
        interface.info(__("You've already created an Android keystore, so I won't create a new one for you."))
        return

    if not interface.yesno(__("I can create an application signing key for you. Signing an application with this key allows it to be placed in the Android Market and other app stores.\n\nDo you want to create a key?")):
        return

    if not interface.yesno(__("I will create the key in the android.keystore file.\n\nYou need to back this file up. If you lose it, you will not be able to upgrade your application.\n\nYou also need to keep the key safe. If evil people get this file, they could make fake versions of your application, and potentially steal your users' data.\n\nWill you make a backup of android.keystore, and keep it in a safe place?")):
        return

    org = interface.input(__("Please enter your name or the name of your organization."))

    dname = "CN=" + org

    if not run(interface, plat.keytool, "-genkey", "-keystore", "android.keystore", "-alias", "android", "-keyalg", "RSA", "-keysize", "2048", "-keypass", "android", "-storepass", "android", "-dname", dname, "-validity", "20000", use_path=True):
        interface.fail(__("Could not create android.keystore. Is keytool in your path?"))

    interface.success(__("I've finished creating android.keystore. Please back it up, and keep it in a safe place."))

def generate_bundle_keys(interface):

    properties = bundle_properties

    set_property(properties, "key.alias", "android")
    set_property(properties, "key.store.password", "android")
    set_property(properties, "key.alias.password", "android")

    default_keystore = plat.path("bundle.keystore").replace("\\", "/")

    set_property(properties, "key.store", default_keystore)

    if get_property(properties, "key.store") != default_keystore:
        return

    if os.path.exists(plat.path("bundle.keystore")):
        return

    dname = "CN=Ren'Py Creator"

    if not run(interface, plat.keytool, "-genkey", "-keystore", "bundle.keystore", "-alias", "android", "-keyalg", "RSA", "-keysize", "2048", "-keypass", "android", "-storepass", "android", "-dname", dname, "-validity", "20000", use_path=True):
        interface.fail(__("Could not create bundle.keystore. Is keytool in your path?"))


def install_sdk(interface):

    # Create the project directory.
    import rapt.build
    rapt.build.copy_project(False)

    check_java(interface)

    unpack_sdk(interface)

    get_packages(interface)

    generate_keys(interface)
    generate_bundle_keys(interface)

    set_property(local_properties, "sdk.dir", plat.sdk.replace("\\", "/"), replace=True)
    set_property(bundle_properties, "sdk.dir", plat.sdk.replace("\\", "/"), replace=True)

    interface.final_success(__("It looks like you're ready to start packaging games."))
