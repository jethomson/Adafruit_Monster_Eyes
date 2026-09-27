# extra_script.py
#
# PlatformIO extra script which creates:
#
#     .pio/build/<environment>/fatfs.bin
#
# from:
#
#     <project>/data/
#
# No external utilities are required.
#
# The filesystem layout is based directly on the known-good
# CircuitPython FAT image supplied by the user.


Import("env")

from pathlib import Path
import os
import struct
import time

MATCH_FILESYSTEM_SIZE_TO_PARTITION_SIZE = True

PARTITION_NAME = "user_fs"
DATA_DIR = Path(env.subst("$PROJECT_DIR"), "data")


# ============================================================================
# Exact filesystem geometry from the known-good image
# ============================================================================

SECTOR_SIZE = 512

SECTORS_PER_CLUSTER = 2
RESERVED_SECTORS = 1
NUM_FATS = 1
ROOT_ENTRIES = 512

MEDIA_DESCRIPTOR = 0xF8

SECTORS_PER_TRACK = 63
NUM_HEADS = 255

HIDDEN_SECTORS = 1

VOLUME_SERIAL = 0xE9216500

VOLUME_LABEL = b"NO NAME    "
FAT_TYPE = b"FAT       "

ROOT_DIR_SECTORS = (
    ROOT_ENTRIES * 32 + SECTOR_SIZE - 1
) // SECTOR_SIZE

CLUSTER_SIZE = (
    SECTOR_SIZE * SECTORS_PER_CLUSTER
)


# ============================================================================
# Derived geometry
# ============================================================================

# All of these values are recalcuated if MATCH_FILESYSTEM_SIZE_TO_PARTITION_SIZE is True

# original CircuitPython file system is 5963776 bytes (about 5.69 MB)
#DOS/MBR boot sector, code offset 0xfe+2, OEM-ID "MSDOS5.0", sectors/cluster 2, FAT  1, root entries 512, sectors 11648 (volumes <=32 MB), Media descriptor 0xf8, sectors/FAT 23, sectors/track 63, heads 255, hidden sectors 1, reserved 0x1, serial number 0xaf096894, unlabeled, FAT (1Y bit by descriptor)
# oddly the fat partition used by CircuitPython was only 3866624 bytes (about 3.69 MB)  user_fs,data,fat,0x450000,0x3B0000,
# these are for reference and testing. they are not recommended because they result in a file system that is too small for all of the eyes
TOTAL_SECTORS = 11648
SECTORS_PER_FAT = 23

DATA_START_SECTOR = (
    RESERVED_SECTORS
    + NUM_FATS * SECTORS_PER_FAT
    + ROOT_DIR_SECTORS
)

# FAT16 uses two-byte FAT entries.
FAT_ENTRY_COUNT = SECTORS_PER_FAT * SECTOR_SIZE // 2

# these are recalculated
DATA_SECTORS = TOTAL_SECTORS - DATA_START_SECTOR
CLUSTER_COUNT = DATA_SECTORS // SECTORS_PER_CLUSTER
IMAGE_SIZE = TOTAL_SECTORS * SECTOR_SIZE


# ============================================================================
# FAT helpers
# ============================================================================

FAT_FREE = 0x0000
FAT_EOC = 0xFFFF



class Fat16Image:
    def __init__(self):
        self.image = bytearray(IMAGE_SIZE)

        # There are CLUSTER_COUNT + 2 usable FAT indexes because
        # cluster numbers start at 2.
        self.fat = [FAT_FREE] * (
            CLUSTER_COUNT + 2
        )

        # FAT16 reserved entries.
        #
        # The first FAT entry contains the media descriptor in the
        # low byte and reserved bits in the upper bits.
        self.fat[0] = 0xFFF8

        self.fat[1] = FAT_EOC

        self.next_cluster = 2

    # ------------------------------------------------------------------------
    # Address conversion
    # ------------------------------------------------------------------------

    def sector_offset(self, sector):
        return sector * SECTOR_SIZE

    def cluster_offset(self, cluster):
        if cluster < 2:
            raise ValueError(
                "Invalid cluster {}".format(cluster)
            )

        if cluster >= len(self.fat):
            raise ValueError(
                "Cluster {} exceeds FAT".format(cluster)
            )

        sector = (
            DATA_START_SECTOR
            + (cluster - 2) * SECTORS_PER_CLUSTER
        )

        return self.sector_offset(sector)

    # ------------------------------------------------------------------------
    # Cluster allocation
    # ------------------------------------------------------------------------

    def allocate_clusters(self, count):
        if count == 0:
            return []

        if self.next_cluster + count > len(self.fat):
            raise RuntimeError(
                f"FAT16 filesystem is full, len(self.fat) {len(self.fat)}"
            )

        clusters = []

        for _ in range(count):
            clusters.append(self.next_cluster)
            self.next_cluster += 1

        for i, cluster in enumerate(clusters):
            if i + 1 < len(clusters):
                self.fat[cluster] = clusters[i + 1]
            else:
                self.fat[cluster] = FAT_EOC

        return clusters

    # ------------------------------------------------------------------------
    # File data
    # ------------------------------------------------------------------------

    def write_file(self, path):
        data = path.read_bytes()

        cluster_count = (
            len(data) + CLUSTER_SIZE - 1
        ) // CLUSTER_SIZE

        clusters = self.allocate_clusters(
            cluster_count
        )

        for index, cluster in enumerate(clusters):
            offset = self.cluster_offset(cluster)

            start = index * CLUSTER_SIZE
            end = start + CLUSTER_SIZE

            chunk = data[start:end]

            self.image[
                offset:
                offset + len(chunk)
            ] = chunk

        return clusters

    # ------------------------------------------------------------------------
    # FAT filename handling
    # ------------------------------------------------------------------------

    @staticmethod
    def make_sfn(name):
        """
        Create a deterministic FAT 8.3 name.

        Long filenames additionally get VFAT LFN entries.
        """

        if name == ".":
            return b".          "

        if name == "..":
            return b"..         "

        stem, ext = os.path.splitext(name)

        if ext.startswith("."):
            ext = ext[1:]

        def clean(s):
            result = []

            for char in s.upper():
                if (
                    "A" <= char <= "Z"
                    or "0" <= char <= "9"
                    or char in "$%'-_@~`!(){}^#&"
                ):
                    result.append(char)
                else:
                    result.append("_")

            return "".join(result)

        stem = clean(stem)
        ext = clean(ext)

        if not stem:
            stem = "_"

        return (
            stem[:8].ljust(8)
            + ext[:3].ljust(3)
        ).encode("ascii")

    @staticmethod
    def is_canonical_sfn(name):
        if name in (".", ".."):
            return True

        sfn = Fat16Image.make_sfn(name)

        stem = sfn[:8].decode(
            "ascii"
        ).rstrip()

        ext = sfn[8:].decode(
            "ascii"
        ).rstrip()

        canonical = stem

        if ext:
            canonical += "." + ext

        return (
            name == canonical
            and len(name) <= 12
            and all(
                ord(c) < 128
                for c in name
            )
        )

    @staticmethod
    def sfn_checksum(sfn):
        checksum = 0

        for value in sfn:
            checksum = (
                ((checksum & 1) << 7)
                | (checksum >> 1)
            )

            checksum = (
                checksum + value
            ) & 0xFF

        return checksum

    @staticmethod
    def make_lfn_entries(name, sfn):
        """
        Generate VFAT LFN entries for name.

        Entries are returned in on-disk order.
        """

        encoded = name.encode(
            "utf-16le"
        )

        units = [
            struct.unpack_from(
                "<H",
                encoded,
                i
            )[0]
            for i in range(
                0,
                len(encoded),
                2
            )
        ]

        # VFAT maximum filename length.
        units = units[:255]

        chunks = [
            units[i:i + 13]
            for i in range(
                0,
                len(units),
                13
            )
        ]

        checksum = Fat16Image.sfn_checksum(
            sfn
        )

        entries = []

        # LFN entries are stored backwards.
        for sequence in range(
            len(chunks),
            0,
            -1
        ):
            entry = bytearray(32)

            sequence_byte = sequence

            if sequence == len(chunks):
                sequence_byte |= 0x40

            entry[0] = sequence_byte

            # LFN attribute.
            entry[11] = 0x0F

            # Type.
            entry[12] = 0

            # Checksum of corresponding SFN.
            entry[13] = checksum

            # First cluster is always zero.
            entry[26:28] = b"\x00\x00"

            values = list(
                chunks[sequence - 1]
            )

            # Add terminating NUL if there is room.
            if len(values) < 13:
                values.append(0)

            # Fill remainder with 0xffff.
            while len(values) < 13:
                values.append(0xFFFF)

            # Positions of the 13 UTF-16 characters.
            positions = (
                list(range(1, 11, 2))
                + list(range(14, 26, 2))
                + list(range(28, 32, 2))
            )

            for position, value in zip(
                positions,
                values
            ):
                struct.pack_into(
                    "<H",
                    entry,
                    position,
                    value
                )

            entries.append(bytes(entry))

        return entries


    @staticmethod
    def volume_label_entry():
        entry = bytearray(32)
        entry[0:11] = b"CIRCUITPY  "
        entry[11] = 0x08
        return bytes(entry)


    # ------------------------------------------------------------------------
    # Directory entry
    # ------------------------------------------------------------------------

    @staticmethod
    def directory_entry(
        name,
        attributes,
        first_cluster,
        file_size,
        timestamp
    ):
        entry = bytearray(32)

        entry[0:11] = Fat16Image.make_sfn(
            name
        )

        entry[11] = attributes

        t = time.localtime(timestamp)

        year = max(
            1980,
            min(2107, t.tm_year)
        )

        month = max(
            1,
            min(12, t.tm_mon)
        )

        day = max(
            1,
            min(31, t.tm_mday)
        )

        fat_date = (
            ((year - 1980) << 9)
            | (month << 5)
            | day
        )

        fat_time = (
            (t.tm_hour << 11)
            | (t.tm_min << 5)
            | (t.tm_sec // 2)
        )

        # Creation time.
        struct.pack_into(
            "<H",
            entry,
            14,
            fat_time
        )

        # Creation date.
        struct.pack_into(
            "<H",
            entry,
            16,
            fat_date
        )

        # Last access date.
        struct.pack_into(
            "<H",
            entry,
            18,
            fat_date
        )

        # FAT16 high cluster word.
        struct.pack_into(
            "<H",
            entry,
            20,
            0
        )

        # Modification time.
        struct.pack_into(
            "<H",
            entry,
            22,
            fat_time
        )

        # Modification date.
        struct.pack_into(
            "<H",
            entry,
            24,
            fat_date
        )

        # First cluster.
        struct.pack_into(
            "<H",
            entry,
            26,
            first_cluster
        )

        # File size.
        struct.pack_into(
            "<I",
            entry,
            28,
            file_size
        )

        return bytes(entry)

    # ------------------------------------------------------------------------
    # Directory creation
    # ------------------------------------------------------------------------

    def build_directory(
        self,
        path,
        parent_cluster
    ):
        children = sorted(
            path.iterdir(),
            key=lambda p: p.name.lower()
        )

        # Estimate how many directory entries are needed.
        required_entries = 2

        for child in children:
            required_entries += 1

            if not self.is_canonical_sfn(
                child.name
            ):
                units = (
                    len(
                        child.name.encode(
                            "utf-16le"
                        )
                    ) // 2
                )

                required_entries += (
                    units + 12
                ) // 13

        entries_per_cluster = (
            CLUSTER_SIZE // 32
        )

        cluster_count = max(
            1,
            (
                required_entries
                + entries_per_cluster
                - 1
            ) // entries_per_cluster
        )

        directory_clusters = (
            self.allocate_clusters(
                cluster_count
            )
        )

        first_cluster = (
            directory_clusters[0]
        )

        entries = []

        # ".".
        entries.append(
            self.directory_entry(
                ".",
                0x10,
                first_cluster,
                0,
                path.stat().st_mtime
            )
        )

        # "..".
        entries.append(
            self.directory_entry(
                "..",
                0x10,
                parent_cluster,
                0,
                path.stat().st_mtime
            )
        )

        for child in children:

            if child.is_dir():

                child_cluster = (
                    self.build_directory(
                        child,
                        first_cluster
                    )
                )

                sfn = self.make_sfn(
                    child.name
                )

                if not self.is_canonical_sfn(
                    child.name
                ):
                    entries.extend(
                        self.make_lfn_entries(
                            child.name,
                            sfn
                        )
                    )

                entries.append(
                    self.directory_entry(
                        child.name,
                        0x10,
                        child_cluster,
                        0,
                        child.stat().st_mtime
                    )
                )

            elif child.is_file():

                data = child.read_bytes()

                clusters = self.write_file(
                    child
                )

                first = (
                    clusters[0]
                    if clusters
                    else 0
                )

                sfn = self.make_sfn(
                    child.name
                )

                if not self.is_canonical_sfn(
                    child.name
                ):
                    entries.extend(
                        self.make_lfn_entries(
                            child.name,
                            sfn
                        )
                    )

                entries.append(
                    self.directory_entry(
                        child.name,
                        0x20,
                        first,
                        len(data),
                        child.stat().st_mtime
                    )
                )

        raw = bytearray(
            cluster_count * CLUSTER_SIZE
        )

        for index, entry in enumerate(
            entries
        ):
            offset = index * 32

            if offset + 32 > len(raw):
                raise RuntimeError(
                    "Directory overflow"
                )

            raw[
                offset:
                offset + 32
            ] = entry

        # Directory terminator.
        if len(entries) * 32 < len(raw):
            raw[len(entries) * 32] = 0x00

        for index, cluster in enumerate(
            directory_clusters
        ):
            offset = self.cluster_offset(
                cluster
            )

            start = index * CLUSTER_SIZE
            end = start + CLUSTER_SIZE

            chunk = raw[start:end]

            self.image[
                offset:
                offset + len(chunk)
            ] = chunk

        return first_cluster

    # ------------------------------------------------------------------------
    # Root directory
    # ------------------------------------------------------------------------

    def build_root(self, data_dir):
        children = sorted(
            data_dir.iterdir(),
            key=lambda p: p.name.lower()
        )

        entries = []

        # FAT root-directory volume label.
        entries.append(
            self.volume_label_entry()
        )

        for child in children:

            if child.is_dir():

                first_cluster = (
                    self.build_directory(
                        child,
                        0
                    )
                )

                sfn = self.make_sfn(
                    child.name
                )

                if not self.is_canonical_sfn(
                    child.name
                ):
                    entries.extend(
                        self.make_lfn_entries(
                            child.name,
                            sfn
                        )
                    )

                entries.append(
                    self.directory_entry(
                        child.name,
                        0x10,
                        first_cluster,
                        0,
                        child.stat().st_mtime
                    )
                )

            elif child.is_file():

                data = child.read_bytes()

                clusters = self.write_file(
                    child
                )

                first_cluster = (
                    clusters[0]
                    if clusters
                    else 0
                )

                sfn = self.make_sfn(
                    child.name
                )

                if not self.is_canonical_sfn(
                    child.name
                ):
                    entries.extend(
                        self.make_lfn_entries(
                            child.name,
                            sfn
                        )
                    )

                entries.append(
                    self.directory_entry(
                        child.name,
                        0x20,
                        first_cluster,
                        len(data),
                        child.stat().st_mtime
                    )
                )

        if len(entries) > ROOT_ENTRIES:
            raise RuntimeError(
                "Root directory requires {} entries; "
                "only {} are available".format(
                    len(entries),
                    ROOT_ENTRIES
                )
            )

        root_sector = (
            RESERVED_SECTORS
            + NUM_FATS * SECTORS_PER_FAT
        )

        root_offset = self.sector_offset(
            root_sector
        )

        for index, entry in enumerate(
            entries
        ):
            offset = root_offset + (
                index * 32
            )

            self.image[
                offset:
                offset + 32
            ] = entry

    # ------------------------------------------------------------------------
    # FAT
    # ------------------------------------------------------------------------

    def write_fat(self):
        fat_offset = self.sector_offset(
            RESERVED_SECTORS
        )

        if len(self.fat) > FAT_ENTRY_COUNT:
            raise RuntimeError(
                f"FAT does not have enough entries, FAT_ENTRY_COUNT {FAT_ENTRY_COUNT}"
            )

        for cluster, value in enumerate(
            self.fat
        ):
            struct.pack_into(
                "<H",
                self.image,
                fat_offset + cluster * 2,
                value
            )

    # ------------------------------------------------------------------------
    # Boot sector
    # ------------------------------------------------------------------------

    def write_boot_sector(self):
        """
        Reproduce the supplied working boot sector.

        Important differences from the previous version:

          * NO separate MBR sector
          * boot sector starts at byte 0
          * EB FE 90 boot code
          * exact BPB values
          * NO NAME volume label
          * FAT type string is "FAT       "
          * zero-filled area from 0x3e through 0x1fd
          * 55 AA at 0x1fe
        """

        boot = bytearray(
            SECTOR_SIZE
        )

        # 00000000
        boot[0:3] = b"\xEB\xFE\x90"

        # 00000003
        boot[3:11] = b"MSDOS5.0"

        # BPB ---------------------------------------------------------------

        # 0x0B: bytes per sector
        struct.pack_into(
            "<H",
            boot,
            0x0B,
            SECTOR_SIZE
        )

        # 0x0D: sectors per cluster
        boot[0x0D] = (
            SECTORS_PER_CLUSTER
        )

        # 0x0E: reserved sectors
        struct.pack_into(
            "<H",
            boot,
            0x0E,
            RESERVED_SECTORS
        )

        # 0x10: number of FATs
        boot[0x10] = NUM_FATS

        # 0x11: root directory entries
        struct.pack_into(
            "<H",
            boot,
            0x11,
            ROOT_ENTRIES
        )

        # 0x13: total sectors (16-bit)
        struct.pack_into(
            "<H",
            boot,
            0x13,
            TOTAL_SECTORS
        )

        # 0x15: media descriptor
        boot[0x15] = MEDIA_DESCRIPTOR

        # 0x16: sectors per FAT
        struct.pack_into(
            "<H",
            boot,
            0x16,
            SECTORS_PER_FAT
        )

        # 0x18: sectors per track
        struct.pack_into(
            "<H",
            boot,
            0x18,
            SECTORS_PER_TRACK
        )

        # 0x1A: number of heads
        struct.pack_into(
            "<H",
            boot,
            0x1A,
            NUM_HEADS
        )

        # 0x1C: hidden sectors
        struct.pack_into(
            "<I",
            boot,
            0x1C,
            HIDDEN_SECTORS
        )

        # 0x20: 32-bit total sectors
        struct.pack_into(
            "<I",
            boot,
            0x20,
            0
        )

        # FAT16 extended BPB -----------------------------------------------

        # Drive number
        boot[0x24] = 0x80

        # Reserved
        boot[0x25] = 0x00

        # Extended boot signature
        boot[0x26] = 0x29

        # Volume serial
        struct.pack_into(
            "<I",
            boot,
            0x27,
            VOLUME_SERIAL
        )

        # Volume label
        boot[0x2B:0x36] = VOLUME_LABEL

        # FAT type
        boot[0x36:0x3E] = FAT_TYPE

        # 0x3E through 0x1FD are zero.
        #
        # This is intentional and matches the supplied image.
        #
        # The boot signature is:
        boot[0x1FE:0x200] = b"\x55\xAA"

        self.image[
            0:SECTOR_SIZE
        ] = boot

    # ------------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------------

    def build(self, data_dir):
        self.write_boot_sector()
        self.build_root(data_dir)
        self.write_fat()

        return bytes(self.image)


# ============================================================================
# PlatformIO integration
# ============================================================================






# ---------------------------------------------------------------------------
# ESP32 partition table parsing
# ---------------------------------------------------------------------------

def parse_size(value):
    """
    Parse ESP32/PlatformIO partition sizes.

    Examples:
        0xEDB000
        0x100000
        1M
        1536K
        1048576
    """
    value = value.strip()

    if not value:
        raise ValueError("Empty partition size")

    if value.lower().startswith("0x"):
        return int(value, 16)

    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([KkMmGg])?", value)
    if not match:
        raise ValueError("Unsupported partition size: %r" % value)

    number = float(match.group(1))
    suffix = (match.group(2) or "").lower()

    multiplier = {
        "": 1,
        "k": 1024,
        "m": 1024 * 1024,
        "g": 1024 * 1024 * 1024,
    }[suffix]

    return int(number * multiplier)


def find_partitions_csv():
    """
    Determine the partition CSV selected by the active PlatformIO
    environment.

    board_build.partitions is normally a project-relative path, but
    PlatformIO can also select a built-in partition table.
    """
    partitions = env.GetProjectOption("board_build.partitions", None)

    if not partitions:
        raise RuntimeError(
            "board_build.partitions is not set in platformio.ini. "
            "Please explicitly select a partition CSV."
        )

    project_dir = env.subst("$PROJECT_DIR")

    candidates = [
        partitions,
        os.path.join(project_dir, partitions),
    ]

    for candidate in candidates:
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)

    # Try PlatformIO's project partitions directory.
    candidates = [
        os.path.join(project_dir, "partitions", partitions),
        os.path.join(project_dir, "boards", partitions),
    ]

    for candidate in candidates:
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)

    raise RuntimeError(
        "Could not locate partition table %r. "
        "Expected a project-relative CSV path." % partitions
    )


def read_user_fs_partition():
    """
    Find:

        user_fs, data, fat, ...

    in the selected ESP32 partition table.

    Returns:
        (offset, size)
    """
    csv_path = find_partitions_csv()

    print("Using partition table: %s" % csv_path)

    with open(csv_path, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            # Remove comments.
            line = line.split("#", 1)[0].strip()

            if not line:
                continue

            fields = [x.strip() for x in line.split(",")]

            if len(fields) < 5:
                continue

            name = fields[0]
            ptype = fields[1].lower()
            subtype = fields[2].lower()
            offset_text = fields[3]
            size_text = fields[4]

            if (
                name == PARTITION_NAME
                and ptype == "data"
                and subtype == "fat"
            ):
                offset = (
                    None
                    if not offset_text
                    else parse_size(offset_text)
                )

                size = parse_size(size_text)

                if offset is None:
                    raise RuntimeError(
                        "Partition %s has no explicit offset "
                        "in %s line %d"
                        % (PARTITION_NAME, csv_path, line_number)
                    )

                return offset, size

    raise RuntimeError(
        "Could not find '%s, data, fat' in %s"
        % (PARTITION_NAME, csv_path)
    )



def generate_fatfs(source, target, env):
    print("")
    print("========== Building user FAT filesystem ==========")


    project_dir = Path(
        env.subst("$PROJECT_DIR")
    )

    build_dir = Path(
        env.subst("$BUILD_DIR")
    )
    print(f"build_dir: {build_dir}")

    partition_offset, partition_size = read_user_fs_partition()

    print(
        "Partition %s:"
        % PARTITION_NAME
    )
    print(
        "  offset = 0x%X" % partition_offset
    )
    print(
        "  size   = 0x%X (%d bytes)"
        % (partition_size, partition_size)
    )

    if not os.path.isdir(DATA_DIR):
        raise RuntimeError(
            "Data directory does not exist: %s" % DATA_DIR
        )

    if partition_size % SECTOR_SIZE:
        raise RuntimeError(
            "FAT partition size 0x%X is not a multiple of "
            "the FAT sector size (%d)"
            % (partition_size, SECTOR_SIZE)
        )

    if MATCH_FILESYSTEM_SIZE_TO_PARTITION_SIZE:
        global TOTAL_SECTORS
        global SECTORS_PER_FAT
        global DATA_START_SECTOR
        global FAT_ENTRY_COUNT
        global DATA_SECTORS
        global CLUSTER_COUNT
        global IMAGE_SIZE

        TOTAL_SECTORS = None
        SECTORS_PER_FAT = None
        DATA_START_SECTOR = None
        FAT_ENTRY_COUNT = None
        DATA_SECTORS = None
        CLUSTER_COUNT = None
        IMAGE_SIZE = None

        TOTAL_SECTORS = partition_size // SECTOR_SIZE
        SECTORS_PER_FAT = 1
        while True:
            DATA_START_SECTOR = (
                RESERVED_SECTORS
                + NUM_FATS * SECTORS_PER_FAT
                + ROOT_DIR_SECTORS
            )
        
            DATA_SECTORS = (
                TOTAL_SECTORS
                - DATA_START_SECTOR
            )
        
            CLUSTER_COUNT = (
                DATA_SECTORS // SECTORS_PER_CLUSTER
            )
        
            required_entries = CLUSTER_COUNT + 2
        
            required_sectors_per_fat = (
                required_entries * 2
                + SECTOR_SIZE - 1
            ) // SECTOR_SIZE
        
            if required_sectors_per_fat == SECTORS_PER_FAT:
                break
        
            SECTORS_PER_FAT = required_sectors_per_fat
        
        FAT_ENTRY_COUNT = SECTORS_PER_FAT * SECTOR_SIZE // 2
        IMAGE_SIZE = TOTAL_SECTORS * SECTOR_SIZE

    print()

    print(f"SECTOR_SIZE: {SECTOR_SIZE}")
    print(f"SECTORS_PER_CLUSTER: {SECTORS_PER_CLUSTER}")
    print(f"NUM_FATS: {NUM_FATS}")
    print(f"ROOT_ENTRIES: {ROOT_ENTRIES}")
    print()
    print(f"TOTAL_SECTORS: {TOTAL_SECTORS}")
    print(f"SECTORS_PER_FAT: {SECTORS_PER_FAT}")
    print(f"DATA_START_SECTOR: {DATA_START_SECTOR}")
    print(f"FAT_ENTRY_COUNT: {FAT_ENTRY_COUNT}")    
    print(f"DATA_SECTORS: {DATA_SECTORS}")
    print(f"CLUSTER_COUNT: {CLUSTER_COUNT}")
    print(f"IMAGE_SIZE: {IMAGE_SIZE}")



    FAT16_MIN_CLUSTERS = 4085
    FAT16_MAX_CLUSTERS = 65524
    
    if not (
        FAT16_MIN_CLUSTERS
        <= CLUSTER_COUNT
        <= FAT16_MAX_CLUSTERS
    ):
        raise RuntimeError(
            "Invalid FAT16 cluster count: {} "
            "(FAT16 requires {}..{} clusters)"
            .format(
                CLUSTER_COUNT,
                FAT16_MIN_CLUSTERS,
                FAT16_MAX_CLUSTERS
            )
        )

    print()
    print(
        "[FATFS] Generating CircuitPython FAT16 image"
    )
    print(
        "[FATFS] source: {}".format(DATA_DIR)
    )

    image = Fat16Image().build(
        DATA_DIR
    )

    output = build_dir / "fatfs.bin"

    output.write_bytes(image)

    print(
        "[FATFS] output: {}".format(output)
    )

    print(
        "[FATFS] size: {} bytes".format(
            len(image)
        )
    )

    print(
        "[FATFS] clusters: {}".format(
            CLUSTER_COUNT
        )
    )

    print()



# Run after the normal PlatformIO build so $BUILD_DIR exists.
#env.AddPostAction("$BUILD_TARGET", generate_fatfs)

env.AddPreAction("buildfs", generate_fatfs)
env.AddPreAction("uploadfs", generate_fatfs)
