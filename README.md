

login page (email, user name, password, register button)  - Dynamo DB 



register page - (Dynamo DB)


main page 

1.User area
2.subscription area (Information saved in Dynamo DB, image saved in S3)
3.query area
4.log out  -> redirect to login page


Ec2 instance - Security Group: HTTP(80), SSH(22)

make S3 -> add html file as website

3-5. CloudFront setting (HTTPS용)

CloudFront → Create Distribution
Origin domain: Choose S3 bucket
Viewer protocol policy: Redirect HTTP to HTTPS
Create Distribution
after deploy I will crete url for example https://xxxx.cloudfront.net 
