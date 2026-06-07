import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure local Hadoop directory for Windows (pyspark requirements)
os.environ["HADOOP_HOME"] = os.path.abspath("hadoop")
os.environ["PATH"] += os.path.pathsep + os.path.abspath("hadoop/bin")

# Create local temp directory for S3 buffering on Windows
os.makedirs(os.path.abspath("hadoop/tmp"), exist_ok=True)

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_unixtime, to_timestamp

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
S3_BUCKET = os.getenv("S3_BUCKET_NAME")

if not AWS_ACCESS_KEY or not AWS_SECRET_KEY or not S3_BUCKET:
    print("Error: Missing AWS credentials or S3 bucket name in .env file.")
    sys.exit(1)

def main():
    print("Initializing PySpark Session with S3 Support...")
    
    # Initialize Spark Session with AWS Hadoop S3A Packages
    spark = SparkSession.builder \
        .appName("StockDataSparkProcess") \
        .config("spark.jars.packages", "org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.access.key", AWS_ACCESS_KEY) \
        .config("spark.hadoop.fs.s3a.secret.key", AWS_SECRET_KEY) \
        .config("spark.hadoop.fs.s3a.endpoint", "s3.amazonaws.com") \
        .config("spark.hadoop.fs.s3a.connection.timeout", "60000") \
        .config("spark.hadoop.fs.s3a.connection.establish.timeout", "50000") \
        .config("spark.hadoop.fs.s3a.connection.request.timeout", "60000") \
        .config("spark.hadoop.fs.s3a.threads.keepalivetime", "60") \
        .config("spark.hadoop.fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider") \
        .config("spark.hadoop.fs.s3a.multipart.purge.age", "86400") \
        .config("spark.hadoop.fs.s3a.socket.timeout", "60000") \
        .config("spark.hadoop.fs.s3a.fast.upload", "true") \
        .config("spark.hadoop.fs.s3a.fast.upload.buffer", "bytebuffer") \
        .config("spark.hadoop.fs.s3a.buffer.dir", os.path.abspath("hadoop/tmp")) \
        .getOrCreate()
        
    print("PySpark Session started successfully!")
    
    # Path to S3 raw JSON files
    s3_raw_path = f"s3a://{S3_BUCKET}/raw/year=*/month=*/day=*/*.json"
    s3_processed_path = f"s3a://{S3_BUCKET}/processed/"
    
    print(f"Reading raw JSON files from: {s3_raw_path} ...")
    try:
        # Read the raw JSON data
        df_raw = spark.read.json(s3_raw_path)
        
        if df_raw.count() == 0:
            print("No raw records found. Make sure the S3 paths match and contain data.")
            spark.stop()
            return
            
        print(f"Loaded {df_raw.count()} raw records from S3.")
        df_raw.printSchema()
        
        # Clean and Type Cast columns
        # Original columns: c (current), d (change), dp (change_percent), h (high), l (low), o (open), pc (prev_close), t (timestamp), symbol, fetched_at
        df_cleaned = df_raw.select(
            col("symbol").cast("string"),
            col("c").cast("double").alias("current_price"),
            col("d").cast("double").alias("change_amount"),
            col("dp").cast("double").alias("change_percent"),
            col("h").cast("double").alias("day_high"),
            col("l").cast("double").alias("day_low"),
            col("o").cast("double").alias("day_open"),
            col("pc").cast("double").alias("prev_close"),
            to_timestamp(from_unixtime(col("t"))).alias("market_timestamp"),
            to_timestamp(from_unixtime(col("fetched_at"))).alias("fetched_at")
        ).filter(col("current_price").isNotNull())
        
        print("\nCleaned and cast schema:")
        df_cleaned.printSchema()
        
        print(f"Writing cleaned data as Parquet to: {s3_processed_path} ...")
        # Overwrite processed partition to keep it fresh
        df_cleaned.write \
            .mode("overwrite") \
            .parquet(s3_processed_path)
            
        print("Spark Processing Job Completed Successfully!")
        
    except Exception as e:
        print(f"An error occurred during PySpark execution: {e}")
        
    finally:
        spark.stop()

if __name__ == "__main__":
    main()
