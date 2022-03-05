#!/usr/bin/env python3

# Copyright (c) 2020-2021 Fpemud <fpemud@sina.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


import os
import re
import abc
import shutil
import parted
import pathlib
from ._util import force_rm, force_mkdir, rmdir_if_empty, compare_files
from ._const import TargetType, TargetAccessMode, PlatformType, PlatformInstallInfo
from ._handy import Handy, Grub
from ._source import Source


class Target(abc.ABC):

    def __init__(self, target_type, target_access_mode, **kwargs):
        assert isinstance(target_type, TargetType)
        assert isinstance(target_access_mode, TargetAccessMode)

        self._targetType = target_type
        self._mode = target_access_mode

        # target specific variables
        if self._targetType == TargetType.MOUNTED_HDD_DEV:
            self._rootfsDir = kwargs.get("rootfs_dir", None)
            self._bootDir = kwargs.get("boot_dir", os.path.join(self._rootfsDir, "boot"))
            self._dev = kwargs["dev"]
        elif self._targetType == TargetType.PYCDLIB_OBJ:
            assert self._mode in [TargetAccessMode.R, TargetAccessMode.W]
            self._iso = kwargs.get["obj"]
        elif self._targetType == TargetType.ISO_DIR:
            self._dir = kwargs["dir"]
            self._bootDir = os.path.join(self._dir, "boot")
        else:
            assert False

        # self._platforms
        self._platforms = dict()
        if self._mode in [TargetAccessMode.R, TargetAccessMode.RW]:
            if self._targetType == TargetType.MOUNTED_HDD_DEV:
                _Common.init_platforms(self)
                for k, v in self._platforms.items():
                    if k == PlatformType.I386_PC:
                        _Bios.check_and_fill_platform_install_info(k, v, self._targetType, self._bootDir, self._dev)
                    elif Handy.isPlatformEfi(k):
                        _Efi.check_and_fill_platform_install_info(k, v, self._targetType, self._bootDir)
                    else:
                        assert False
            elif self._targetType == TargetType.PYCDLIB_OBJ:
                assert False                                                    # FIXME
            elif self._targetType == TargetType.ISO_DIR:
                _Common.init_platforms(self)
                for k, v in self._platforms.items():
                    if k == PlatformType.I386_PC:
                        _Bios.check_and_fill_platform_install_info(k, v, self._targetType, self._bootDir, None)
                    elif Handy.isPlatformEfi(k):
                        _Efi.check_and_fill_platform_install_info(k, v, self._targetType, self._bootDir)
                    else:
                        assert False
            else:
                assert False

    @property
    def target_type(self):
        return self._targetType

    @property
    def target_access_mode(self):
        return self._mode

    @property
    def platforms(self):
        return self._platforms.keys()

    @property
    def bootable_platforms(self):
        return [k for k, v in self._platforms.items() if v.status == PlatformInstallInfo.Status.BOOTABLE]

    def get_platform_install_info(self, platform_type):
        assert isinstance(platform_type, PlatformType)

        if platform_type in self._platforms:
            return self._platforms[platform_type]
        else:
            ret = PlatformInstallInfo()
            ret.status = PlatformInstallInfo.Status.NOT_EXIST
            return ret

    def install_platform(self, platform_type, source, **kwargs):
        assert self._mode in [TargetAccessMode.RW, TargetAccessMode.W]
        assert self.get_platform_install_info(platform_type).status != PlatformInstallInfo.Status.BOOTABLE
        assert isinstance(source, Source)

        ret = PlatformInstallInfo()
        ret.status = PlatformInstallInfo.Status.BOOTABLE

        if self._targetType == TargetType.MOUNTED_HDD_DEV:
            _Common.install_platform(self, platform_type, source)
            if platform_type == PlatformType.I386_PC:
                _Bios.install_platform(platform_type, ret, source, self._bootDir, self._dev,
                                       True,                                                # bInstallMbr
                                       False,                                               # bFloppyOrHdd
                                       kwargs.get("allow_floppy", False),
                                       kwargs.get("rs_codes", True))
            elif Handy.isPlatformEfi(platform_type):
                _Efi.install_platform(platform_type, ret, source, self._bootDir)
            else:
                assert False
        elif self._targetType == TargetType.PYCDLIB_OBJ:
            # FIXME
            assert False
        elif self._targetType == TargetType.ISO_DIR:
            _Common.install_platform(self, platform_type, source)
            if platform_type == PlatformType.I386_PC:
                _Bios.install_platform(platform_type, ret, source, self._bootDir, self._dev,
                                       False,                                               # bInstallMbr
                                       False,                                               # bFloppyOrHdd
                                       kwargs.get("allow_floppy", False),
                                       kwargs.get("rs_codes", True))
            elif Handy.isPlatformEfi(platform_type):
                _Efi.install_platform(platform_type, ret, source, self._bootDir)
            else:
                assert False
        else:
            assert False

        self._platforms[platform_type] = ret

    def remove_platform(self, platform_type):
        assert self._mode in [TargetAccessMode.RW, TargetAccessMode.W]
        assert isinstance(platform_type, PlatformType)
        
        if self._targetType == TargetType.MOUNTED_HDD_DEV:
            if platform_type == PlatformType.I386_PC:
                _Bios.remove_platform(platform_type, self._dev)
            elif Handy.isPlatformEfi(platform_type):
                _Efi.remove_platform(platform_type, self._bootDir)
            else:
                assert False
            _Common.remove_platform(self, platform_type)
        elif self._targetType == TargetType.PYCDLIB_OBJ:
            # FIXME
            assert False
        elif self._targetType == TargetType.ISO_DIR:
            _Common.remove_platform(self, platform_type)
        else:
            assert False

        if platform_type in self._platforms:
            del self._platforms[platform_type]

    def install_data(self, source, locales=None, fonts=None, themes=None):
        assert self._mode in [TargetAccessMode.RW, TargetAccessMode.W]

        grubDir = os.path.join(self._bootDir, "grub")
        force_mkdir(grubDir)

        if locales is not None:
            Grub.copyLocaleFiles(source, grubDir, locales)
        if fonts is not None:
            Grub.copyFontFiles(source, grubDir, fonts)
        if themes is not None:
            Grub.copyThemeFiles(source, grubDir, themes)

    def remove_data(self):
        assert self._mode in [TargetAccessMode.RW, TargetAccessMode.W]

        grubDir = os.path.join(self._bootDir, "grub")
        force_rm(os.path.join(grubDir, "locale"))
        force_rm(os.path.join(grubDir, "fonts"))
        force_rm(os.path.join(grubDir, "themes"))

    def touch_env_file(self):
        assert self._mode in [TargetAccessMode.RW, TargetAccessMode.W]

        grubEnvFile = os.path.join(self._bootDir, "grub", "grubenv")
        if not os.path.exists(grubEnvFile):
            Grub.createEnvBlkFile(grubEnvFile)

    def remove_env_file(self):
        assert self._mode in [TargetAccessMode.RW, TargetAccessMode.W]

        grubEnvFile = os.path.join(self._bootDir, "grub", "grubenv")
        force_rm(grubEnvFile)

    def remove_all(self):
        assert self._mode in [TargetAccessMode.RW, TargetAccessMode.W]

        # remove platforms, some platform needs special processing
        for k in list(self._platforms.keys()):
            self.remove_platform(k)

        # remove remaining files
        _Efi.remove_remaining_crufts(self._bootDir)
        _Common.remove_remaining_crufts(self)

    def check(self, auto_fix=False):
        assert self._mode in [TargetAccessMode.R, TargetAccessMode.RW]

        if self._targetType == TargetType.MOUNTED_HDD_DEV:
            _Common.check(self, auto_fix)
        elif self._targetType == TargetType.PYCDLIB_OBJ:
            # FIXME
            assert False
        elif self._targetType == TargetType.ISO_DIR:
            _Common.check(self, auto_fix)
        else:
            assert False

    def check_with_source(self, source, auto_fix=False):
        assert self._mode in [TargetAccessMode.R, TargetAccessMode.RW]
        assert isinstance(source, Source)

        if self._targetType == TargetType.MOUNTED_HDD_DEV:
            _Common.check_with_source(self, source, auto_fix)
        elif self._targetType == TargetType.PYCDLIB_OBJ:
            # FIXME
            assert False
        elif self._targetType == TargetType.ISO_DIR:
            _Common.check_with_source(self, source, auto_fix)
        else:
            assert False


class _Common:

    @staticmethod
    def init_platforms(p):
        grubDir = os.path.join(p._bootDir, "grub")
        if os.path.isdir(grubDir):
            for fn in os.listdir(grubDir):
                for pt in PlatformType:
                    if fn == pt.value:
                        p._platforms[pt] = PlatformInstallInfo()
                        p._platforms[pt].status = PlatformInstallInfo.Status.BOOTABLE

    @staticmethod
    def install_platform(p, platform_type, source):
        mnt = Grub.probeMnt(p._bootDir)
        if mnt.fs_uuid is None:
            raise Exception("")     # FIXME

        grubDir = os.path.join(p._bootDir, "grub")
        relGrubDir = grubDir.replace(mnt.mnt_pt, "")

        moduleList = []

        # disk module
        if platform_type == PlatformType.I386_PC:
            disk_module = "biosdisk"
        elif platform_type == PlatformType.I386_MULTIBOOT:
            disk_module = "native"
        elif Handy.isPlatformCoreboot(platform_type):
            disk_module = "native"
        elif Handy.isPlatformQemu(platform_type):
            disk_module = "native"
        elif platform_type == PlatformType.MIPSEL_LOONGSON:
            disk_module = "native"
        else:
            disk_module = None

        if disk_module is None:
            pass
        elif disk_module == "biosdisk":
            moduleList.append("biosdisk")
        elif disk_module == "native":
            moduleList += ["pata"]                              # for IDE harddisk
            moduleList += ["ahci"]                              # for SCSI harddisk
            moduleList += ["ohci", "uhci", "ehci", "ubms"]      # for USB harddisk
        else:
            assert False

        # fs module
        if Handy.isPlatformEfi(platform_type):
            if mnt.fs != "vfat":
                raise Exception("%s doesn't look like an EFI partition" % (p._bootDir))
        moduleList.append(Grub.getGrubFsName(mnt.fs))

        # install files
        Grub.copyPlatformFiles(platform_type, source, grubDir)

        # generate load.cfg for core.img
        loadCfgFile = os.path.join(grubDir, platform_type.value, "load.cfg")
        with open(loadCfgFile, "w") as f:
            moduleList.append("search_fs_uuid")
            f.write("search.fs_uuid %s root %s\n" % (mnt.fs_uuid, ""))  # FIXME: should add hints to raise performance
            f.write("set prefix=($root)'%s'\n" % (relGrubDir))          # FIXME: relGrubDir should be escaped

        # make core.img
        coreName, mkimageTarget = Grub.getCoreImgNameAndTarget()
        coreImgFile = os.path.join(grubDir, platform_type.value, coreName)
        Grub.makeCoreImage(source, platform_type, loadCfgFile, mkimageTarget, moduleList, coreImgFile)

    @staticmethod
    def remove_platform(p, platform_type):
        platDir = os.path.join(p._bootDir, "grub", platform_type.value)
        force_rm(platDir)

    @staticmethod
    def remove_remaining_crufts(p):
        force_rm(os.path.join(p._bootDir, "grub"))

    @staticmethod
    def check(p, auto_fix):
        grubDir = os.path.join(p._bootDir, "grub")
        if os.path.isdir(grubDir):
            pset = set([x.value for x in p._platforms])
            fset = set(os.listdir(grubDir)) - set(["locale", "fonts", "themes"])
            # FIXME: check every platform
            # FIXME: check redundant files
        else:
            if len(p._platforms) > 0:
                raise Exception("")     # FIXME

    @staticmethod
    def check_with_source(p, source, auto_fix):
        # FIXME
        pass


class _Bios:

    @classmethod
    def check_and_fill_platform_install_info(cls, platform_type, platform_install_info, target_type, bootDir, dev):
        assert platform_install_info.status == platform_install_info.Status.BOOTABLE

        coreImgFile = os.path.join(bootDir, "grub", "core.img")
        bootImgFile = os.path.join(bootDir, "grub", "boot.img")
        bAllowFloppy = None

        bOk = False
        while True:
            if not os.path.exists(bootImgFile):
                break
            bootBuf = pathlib.Path(bootImgFile).read_bytes()
            if len(bootBuf) != Grub.DISK_SECTOR_SIZE:
                break

            if not os.path.exists(coreImgFile):
                break
            coreBuf = pathlib.Path(coreImgFile).read_bytes()
            if not (Grub.DISK_SECTOR_SIZE <= len(coreBuf) <= cls._getMbrGapSizeThreshold()):
                break

            with open(dev, "rb") as f:
                tmpBuf = f.read(Grub.DISK_SECTOR_SIZE)

                s1, e1 = Grub.BOOT_MACHINE_BPB_START, Grub.BOOT_MACHINE_BPB_END
                if tmpBuf[:s1] != bootBuf[:s1]:
                    break

                s2, e2 = Grub.BOOT_MACHINE_DRIVE_CHECK, Grub.BOOT_MACHINE_DRIVE_CHECK + 2
                if tmpBuf[e1:s2] != bootBuf[e1:s2]:
                    break
                if tmpBuf[s2:e2] == b'\x90\x90':
                    bAllowFloppy = False
                else:
                    if tmpBuf[s2:e2] != bootBuf[s2:e2]:
                        break
                    bAllowFloppy = True

                s3, e3 = Grub.BOOT_MACHINE_WINDOWS_NT_MAGIC, Grub.BOOT_MACHINE_PART_END
                if tmpBuf[e2:s3] != bootBuf[e2:s3]:
                    break

                if tmpBuf[e3:] != bootBuf[e3:]:
                    break

                if coreBuf != f.read(len(coreBuf)):
                    break

            bOk = True

        if bOk:
            # check success
            platform_install_info.mbr_installed = True
            platform_install_info.allow_floppy = bAllowFloppy
            platform_install_info.rs_codes = False
        else:
            # check failed
            platform_install_info.status = platform_install_info.Status.EXIST

    @classmethod
    def install_platform(cls, platform_type, platform_install_info, source, bootDir, dev, bInstallMbr, bFloppyOrHdd, bAllowFloppy, bAddRsCodes):
        assert _Bios._isValidDisk(dev)
        assert not bFloppyOrHdd and not bAllowFloppy and not bAddRsCodes

        coreImgFile = os.path.join(bootDir, "grub", "core.img")
        bootImgFile = os.path.join(bootDir, "grub", "boot.img")

        # copy boot.img file
        shutil.copy(os.path.join(source.get_platform_dir(platform_type), "boot.img"), bootImgFile)

        # install into device bios mbr
        if bInstallMbr:
            bootBuf = pathlib.Path(bootImgFile).read_bytes()
            if len(bootBuf) != Grub.DISK_SECTOR_SIZE:
                raise Exception("the size of '%s' is not %u" % (bootImgFile, Grub.DISK_SECTOR_SIZE))

            coreBuf = pathlib.Path(coreImgFile).read_bytes()
            if len(coreBuf) < Grub.DISK_SECTOR_SIZE:
                raise Exception("the size of '%s' is too small" % (coreImgFile))
            if len(coreBuf) > cls._getMbrGapSizeThreshold():
                raise Exception("the size of '%s' is too large" % (coreImgFile))

            bootBuf = bytearray(bootBuf)
            with open(dev, "rb") as f:
                tmpBuf = f.read(Grub.DISK_SECTOR_SIZE)

                # Copy the possible DOS BPB.
                s, e = Grub.BOOT_MACHINE_BPB_START, Grub.BOOT_MACHINE_BPB_END
                bootBuf[s:e] = tmpBuf[s:e]

                # If DEST_DRIVE is a hard disk, enable the workaround, which is
                # for buggy BIOSes which don't pass boot drive correctly. Instead,
                # they pass 0x00 or 0x01 even when booted from 0x80.
                if not bAllowFloppy and not bFloppyOrHdd:
                    # Replace the jmp (2 bytes) with double nop's.
                    bootBuf[Grub.BOOT_MACHINE_DRIVE_CHECK] = 0x90
                    bootBuf[Grub.BOOT_MACHINE_DRIVE_CHECK+1] = 0x90

                # Copy the partition table.
                if not bAllowFloppy and not bFloppyOrHdd:
                    s, e = Grub.BOOT_MACHINE_WINDOWS_NT_MAGIC, Grub.BOOT_MACHINE_PART_END
                    bootBuf[s:e] = tmpBuf[s:e]

            with open(dev, "wb") as f:
                if bAddRsCodes:
                    assert False
                else:
                    f.write(bootBuf)
                    f.write(coreBuf)

        # fill custom attributes
        platform_install_info.mbr_installed = bInstallMbr
        platform_install_info.allow_floppy = bAllowFloppy
        platform_install_info.rs_codes = bAddRsCodes

    @staticmethod
    def remove_platform(platform_type, bootDir):
        pass

    @staticmethod
    def _getMbrGapSizeThreshold():
        return 512 * 1024

    @classmethod
    def _isValidDisk(cls, dev):
        if not re.fullmatch(".*[0-9]+$", dev):
            return False                            # dev should be a disk, not partition
        pDev = parted.getDevice(dev)
        pDisk = parted.newDisk(pDev)
        if pDisk.type != "msdos":
            return False                            # dev should have mbr partition table
        pPartiList = pDisk.getPrimaryPartitions()
        if len(pPartiList) > 0:
            return False                            # dev should have partitions
        if pPartiList[0].geometry.start * pDev.sectorSize < cls._getMbrGapSizeThreshold():
            return False                            # dev should have mbr gap
        return True


class _Efi:

    """We only support removable, and not upgrading NVRAM"""

    @staticmethod
    def check_and_fill_platform_install_info(platform_type, platform_install_info, target_type, bootDir):
        assert platform_install_info.status == platform_install_info.Status.BOOTABLE

        coreFullfn = os.path.join(bootDir, "grub", platform_type.value, Grub.getCoreImgNameAndTarget()[0])
        efiFullfn = os.path.join(bootDir, "EFI", "BOOT", Handy.getStandardEfiFilename(platform_type))

        # check
        bOk = True
        if bOk and not os.path.exists(efiFullfn):
            bOk = False
        if bOk and not compare_files(coreFullfn, efiFullfn):
            bOk = False

        if bOk:
            # check success
            platform_install_info.removable = True
            platform_install_info.nvram = False
        else:
            # check failed
            platform_install_info.status = platform_install_info.Status.EXIST

    @staticmethod
    def install_platform(platform_type, platform_install_info, source, bootDir):
        grubPlatDir = os.path.join(bootDir, "grub", platform_type.value)
        efiDir = os.path.join(bootDir, "EFI")
        efiDirLv2 = os.path.join(bootDir, "EFI", "BOOT")
        efiFn = Handy.getStandardEfiFilename(platform_type)

        # create efi dir
        force_mkdir(efiDir)

        # create level 2 efi dir
        force_mkdir(efiDirLv2)

        # copy efi file
        coreName = Grub.getCoreImgNameAndTarget()[0]
        shutil.copy(os.path.join(grubPlatDir, coreName), os.path.join(efiDirLv2, efiFn))

        # fill custom attributes
        platform_install_info.removable = True
        platform_install_info.nvram = False

    @staticmethod
    def remove_platform(platform_type, bootDir):
        efiDir = os.path.join(bootDir, "EFI")
        efiDirLv2 = os.path.join(bootDir, "EFI", "BOOT")
        efiFn = Handy.getStandardEfiFilename(platform_type)

        # remove efi file
        force_rm(os.path.join(efiDirLv2, efiFn))

        # remove empty level 2 efi dir
        rmdir_if_empty(efiDirLv2)

        # remove empty efi dir
        rmdir_if_empty(efiDir)

    @staticmethod
    def remove_remaining_crufts(bootDir):
        force_rm(os.path.join(bootDir, "EFI"))


# class _Sparc:
#
#     @staticmethod
#     def install_platform(p, platform_type, source):
#         grub_util_sparc_setup("boot.img", "core.img", dev, force?, fs_probe?, allow_floppy?, add_rs_codes?, )
#         grub_set_install_backup_ponr()





#     @staticmethod
#     def install_platform_for_iso(platform_type, source, bootDir, dev, bHddOrFloppy, bInstallMbr):

#         if 



#         char *output = grub_util_path_concat (3, boot_grub, "i386-pc", "eltorito.img");
#       load_cfg = grub_util_make_temporary_file ();



#       grub_install_push_module ("biosdisk");
#       grub_install_push_module ("iso9660");
#       grub_install_make_image_wrap (source_dirs[GRUB_INSTALL_PLATFORM_I386_PC],
# 				    "/boot/grub", output,
# 				    0, load_cfg,
# 				    "i386-pc-eltorito", 0);
#       xorriso_push ("-boot-load-size");
#       xorriso_push ("4");
#       xorriso_push ("-boot-info-table");

# 	      char *boot_hybrid = grub_util_path_concat (2, source_dirs[GRUB_INSTALL_PLATFORM_I386_PC],
# 							 "boot_hybrid.img");
# 	      xorriso_push ("--grub2-boot-info");
# 	      xorriso_push ("--grub2-mbr");
# 	      xorriso_push (boot_hybrid);

#   /** build multiboot core.img */
#   grub_install_push_module ("pata");
#   grub_install_push_module ("ahci");
#   grub_install_push_module ("at_keyboard");
#   make_image (GRUB_INSTALL_PLATFORM_I386_MULTIBOOT, "i386-multiboot", "i386-multiboot/core.elf");
#   grub_install_pop_module ();
#   grub_install_pop_module ();
#   grub_install_pop_module ();
#   make_image_fwdisk (GRUB_INSTALL_PLATFORM_I386_IEEE1275, "i386-ieee1275", "ofwx86.elf");

#   grub_install_push_module ("part_apple");
#   make_image_fwdisk (GRUB_INSTALL_PLATFORM_POWERPC_IEEE1275, "powerpc-ieee1275", "powerpc-ieee1275/core.elf");
#   grub_install_pop_module ();

#   make_image_fwdisk (GRUB_INSTALL_PLATFORM_SPARC64_IEEE1275,
# 		     "sparc64-ieee1275-cdcore", "sparc64-ieee1275/core.img");






# self.pubkey = XXX         # --pubkey=FILE
# self.compress = XXX       # --compress=no|xz|gz|lzo

# we won't support:
# 1. 








# ia64-efi

# mips-arc
# mips-qemu_mips-flash
# mips-qemu_mips-elf

# mipsel-arc
# mipsel-fuloong2f-flash
# mipsel-loongson
# mipsel-loongson-elf
# mipsel-qemu_mips-elf
# mipsel-qemu_mips-flash
# mipsel-yeeloong-flash

# powerpc-ieee1275

# riscv32-efi

# riscv64-efi

# sparc64-ieee1275-raw
# sparc64-ieee1275-cdcore
# sparc64-ieee1275-aout


