import os
import urllib.request

def setup_hadoop():
    workspace_dir = os.path.abspath(os.path.dirname(__file__))
    hadoop_dir = os.path.join(workspace_dir, "hadoop")
    bin_dir = os.path.join(hadoop_dir, "bin")
    
    os.makedirs(bin_dir, exist_ok=True)
    
    # URLs for Hadoop 3.3.0 winutils binaries
    winutils_url = "https://github.com/kontext-tech/winutils/raw/master/hadoop-3.3.0/bin/winutils.exe"
    hadoop_dll_url = "https://github.com/kontext-tech/winutils/raw/master/hadoop-3.3.0/bin/hadoop.dll"
    
    winutils_path = os.path.join(bin_dir, "winutils.exe")
    hadoop_dll_path = os.path.join(bin_dir, "hadoop.dll")
    
    print("Downloading winutils.exe...")
    urllib.request.urlretrieve(winutils_url, winutils_path)
    
    print("Downloading hadoop.dll...")
    urllib.request.urlretrieve(hadoop_dll_url, hadoop_dll_path)
    
    print("\nSetup complete!")
    print(f"Hadoop binaries downloaded to: {bin_dir}")
    print("\nTo use this in your Python scripts, add these lines at the very top of your script:")
    print("----------------------------------------------------------------------------")
    print("import os")
    print(f'os.environ["HADOOP_HOME"] = os.path.abspath("hadoop")')
    print(f'os.environ["PATH"] += os.path.pathsep + os.path.abspath("hadoop/bin")')
    print("----------------------------------------------------------------------------")

if __name__ == "__main__":
    setup_hadoop()
