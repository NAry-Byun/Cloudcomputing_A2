
1. Create frontend 
login page (email, user name, password, register button)  - Dynamo DB 
register page - (Dynamo DB)
main page 
1.User area
2.subscription area (Information saved in Dynamo DB, image saved in S3)
3.query area
4.log out  -> redirect to login page


2. upload frontend file and image script in S3( 2 different S3 bucket need to create)make S3 -> add html file as website

2. Upload frontend files and image script to S3 (two separate S3 buckets) and configure S3 static website hosting

Bushra, for the S3 section:

I created two S3 buckets, one for the frontend website and one for artist images.
I uploaded the frontend HTML, CSS, and JavaScript files to the website bucket and enabled static website hosting. 
I also ran a Python script to download the artist images from the dataset and upload them to the image bucket, which created an updated songs JSON file with S3 image URLs. I then created and loaded the DynamoDB tables: 
`Users`, `Music`, and `UserSubscriptions`.

<img width="560" height="460" alt="Screenshot 2026-04-19 at 12 01 55 AM" src="https://github.com/user-attachments/assets/33cc8709-f45f-43bf-b6ff-d4908fa53822" />

This proves the artist images were uploaded successfully to the musicly-images S3 bucket.




<img width="1369" height="564" alt="Screenshot 2026-04-19 at 12 02 10 AM" src="https://github.com/user-attachments/assets/43e89c33-6cc8-4565-9c92-7e77def95abb" />
This proves the bucket structure was created correctly.

next step is the API/backend connection.

3. set up Dynamo DB and rest API
Step 1 — REST API creation-> AWS Console → API Gateway → Create API → REST API → Build


4. Ec2 instance - Security Group: HTTP(80), SSH(22)


5. CloudFront setting

CloudFront → Create Distribution
Origin domain: Choose S3 bucket
Viewer protocol policy: Redirect HTTP to HTTPS
Create Distribution
after deploy I will crete url for example https://xxxx.cloudfront.net 
