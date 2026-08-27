import argparse
import os
from datetime import datetime


def logrotate(log_file):
  max_filesize = 1 * 1024 * 1024 * 1024 #1GB
  if os.path.exists(log_file):
    size = os.path.getsize(log_file)
    if size > max_filesize:
      timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
      new_log_file = f"{log_file}.{timestamp}"
      os.rename(log_file, new_log_file)
      open(log_file, 'w').close()
      print(f"Log file '{log_file}' has been rotated to '{new_log_file}'")
    else:
      print(f"Log file '{log_file}' is not large enough to rotate")
  else:
    print(f"Log file '{log_file}' does not exist")

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Log Rotate Script')
  parser.add_argument(
    '--logfile',
    type=str,
    default="/tmp/sample.log",
    help='Enter the log filename'
  )
  args = parser.parse_args([])
  #open(args.logfile, 'w').close()
  
  logrotate(args.logfile)
