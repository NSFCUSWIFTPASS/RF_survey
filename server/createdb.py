from configparser import ConfigParser
import psycopg2
import json

def config(filename="/home/tschimben/Documents/database.ini", section="postgresql"):
    # create a parser
    parser = ConfigParser()
    # read config file
    parser.read(filename)

    # get section, default to postgresql
    db = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            db[param[0]] = param[1]
    else:
        raise Exception("Section {0} not found in the {1} file".format(section, filename))

    return db

def create_tables():
    """create tables in the PostgreSQL database"""

    commands =(
         """
        CREATE TABLE IF NOT EXISTS status_codes (
            code_id INTEGER NOT NULL PRIMARY KEY,
            description TEXT NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS storage (
            mount_id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            nfs_mnt VARCHAR(255) NOT NULL UNIQUE,
            local_mnt VARCHAR(255) NOT NULL,
            storage_cap BIGINT NOT NULL,
            op_status INTEGER NOT NULL,
            CONSTRAINT fk_status
                FOREIGN KEY (op_status)
                REFERENCES status_codes(code_id)
                ON DELETE CASCADE
                ON UPDATE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS hardware (
            hardware_id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            location POINT NOT NULL,
            enclosure BOOLEAN NOT NULL,
            op_status INTEGER NOT NULL,
            mount_id INTEGER NOT NULL,
            CONSTRAINT fk_mount
                FOREIGN KEY (mount_id)
                REFERENCES storage(mount_id)
                ON DELETE CASCADE
                ON UPDATE CASCADE,
            CONSTRAINT fk_status
                FOREIGN KEY (op_status)
                REFERENCES status_codes(code_id)
                ON DELETE CASCADE
                ON UPDATE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS status (
            status_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            hostname VARCHAR(100) NOT NULL,
            time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            rpi_cpu_temp NUMERIC NOT NULL,
            sdr_temp NUMERIC NOT NULL,
            avg_cpu_usage NUMERIC NOT NULL,
            bytes_recorded BIGINT NOT NULL,
            rem_nfs_storage_cap BIGINT NOT NULL,
            rem_rpi_storage_cap BIGINT NOT NULL,
            rpi_uptime_minutes BIGINT NOT NULL,
            hardware_id INTEGER NOT NULL,
            wr_servo_state VARCHAR(50),
            wr_sfp1_link BOOLEAN,
            wr_sfp2_link BOOLEAN,
            wr_sfp1_tx BIGINT,
            wr_sfp1_rx BIGINT,
            wr_sfp2_tx BIGINT,
            wr_sfp2_rx BIGINT,
            wr_phase_setp INT,
            wr_rtt INT,
            wr_crtt INT,
            wr_clck_offset INT,
            wr_updt_cnt INT,
            wr_temp NUMERIC,
            wr_host VARCHAR(100),
            CONSTRAINT fk_hardware
                FOREIGN KEY (hardware_id)
                REFERENCES hardware(hardware_id)
                ON DELETE CASCADE
                ON UPDATE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS rpi (
            rpi_id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            hostname VARCHAR(100) NOT NULL UNIQUE,
            rpi_ip INET NOT NULL,
            rpi_mac MACADDR NOT NULL,
            rpi_v VARCHAR(255) NOT NULL,
            os_v VARCHAR(255) NOT NULL,
            memory BIGINT NOT NULL,
            storage_cap BIGINT NOT NULL,
            cpu_type VARCHAR(255) NOT NULL,
            cpu_cores INTEGER NOT NULL,
            op_status INTEGER NOT NULL,
            hardware_id INTEGER NOT NULL,
            CONSTRAINT fk_hardware
                FOREIGN KEY (hardware_id)
                REFERENCES hardware(hardware_id)
                ON DELETE CASCADE
                ON UPDATE CASCADE,
            CONSTRAINT fk_status
                FOREIGN KEY (op_status)
                REFERENCES status_codes(code_id)
                ON DELETE CASCADE
                ON UPDATE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS sdr (
            sdr_id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            sdr_serial CHAR(7) NOT NULL UNIQUE,
            mboard_name VARCHAR(255) NOT NULL,
            external_clock BOOLEAN NOT NULL,
            op_status INTEGER NOT NULL,
            hardware_id INTEGER NOT NULL,
            CONSTRAINT fk_hardware
                FOREIGN KEY (hardware_id)
                REFERENCES hardware(hardware_id)
                ON DELETE CASCADE
                ON UPDATE CASCADE,
            CONSTRAINT fk_status
                FOREIGN KEY (op_status)
                REFERENCES status_codes(code_id)
                ON DELETE CASCADE
                ON UPDATE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS wrlen (
            wr_id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            wr_serial VARCHAR(100) UNIQUE,
            wr_ip INET,
            wr_mac MACADDR,
            mode VARCHAR(100),
            wr_host VARCHAR(100),
            op_status INTEGER NOT NULL,
            hardware_id INTEGER NOT NULL,
            CONSTRAINT fk_hardware
                FOREIGN KEY (hardware_id)
                REFERENCES hardware(hardware_id)
                ON DELETE CASCADE
                ON UPDATE CASCADE,
            CONSTRAINT fk_status
                FOREIGN KEY (op_status)
                REFERENCES status_codes(code_id)
                ON DELETE CASCADE
                ON UPDATE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS metadata(
            metadata_id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            org VARCHAR(100) NOT NULL,
            frequency BIGINT NOT NULL,
            sample_rate BIGINT NOT NULL,
            bandwidth BIGINT NOT NULL,
            gain INTEGER NOT NULL,
            length NUMERIC NOT NULL,
            interval NUMERIC NOT NULL,
            bit_depth VARCHAR(10),
            UNIQUE(org, frequency, sample_rate, bandwidth, gain, length, interval, bit_depth)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS recordings(
            recording_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            hardware_id INTEGER NOT NULL,
            metadata_id INTEGER NOT NULL,
            file_name VARCHAR(100) NOT NULL UNIQUE,
            file_path VARCHAR(255) NOT NULL,
            survey_id CHAR(6) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            entered_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_hardware
                FOREIGN KEY (hardware_id)
                REFERENCES hardware(hardware_id)
                ON DELETE CASCADE
                ON UPDATE CASCADE,
            CONSTRAINT fk_metadata
                FOREIGN KEY (metadata_id)
                REFERENCES metadata(metadata_id)
                ON DELETE CASCADE

        );
        """,
        """
        CREATE TABLE IF NOT EXISTS outputs(
            output_id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            recording_id INTEGER NOT NULL UNIQUE,
            average_db NUMERIC(21,16) NOT NULL,
            max_db NUMERIC(21,16) NOT NULL,
            median_db NUMERIC(21,16) NOT NULL,
            std_dev NUMERIC NOT NULL,
            kurtosis NUMERIC NOT NULL,
            CONSTRAINT fk_recording
                FOREIGN KEY (recording_id)
                REFERENCES recordings(recording_id)
                ON DELETE CASCADE
                ON UPDATE CASCADE
        );
        """,
        """INSERT INTO status_codes(code_id, description)
            VALUES('0', 'offline'),('1', 'online and functional'),('2', 'survey running'),('3', 'unresponsive'),('4', 'storage below 10% capacity'),('5', 'storage full'),('6', 'SDR / WR-LEN issues'),('7', 'temperature above threshold'),('8', 'unidentified error, component needs attention'),('9', 'component removed and under repair');
        """
        )

#def connect():
   # """ Connect to the PostgreSQL database server"""

    conn = None
    try:
        # read connection parameters
        params = config()
        # connect to the PostgreSQL server
        print("Connecting to the PostgreSQL database...")
        conn = psycopg2.connect(**params)
        # create a cursor
        cur = conn.cursor()
        # execute a statement
        print("Connection Successful.")
        #cur.execute("SELECT version()")
        for command in commands:
            cur.execute(command)
        # display the PostgreSQL database server version
        # close the communication with the PostgreSQL server
        cur.close()
        conn.commit()
        print("Commands executed.")
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    create_tables()
