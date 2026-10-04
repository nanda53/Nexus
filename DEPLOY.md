# Deploying Nexus on AWS

Architecture of this demo:

    Browser --HTTPS--> CloudFront --HTTP--> EC2 (Docker Compose)
                                             |- nginx + React (static build)
                                             |- FastAPI (/api)
                                             |- PostgreSQL (ledger)
                                             '- Redis (idempotency locks)

Only port 80 is open on the server; Postgres and Redis are not reachable from the internet.
The full production design (S3, Fargate + ALB, RDS Multi-AZ, ElastiCache, private subnets)
is the scale-up path; this is the cost-optimised version of it for the demo.

## Before you start
1. Push this project to GitHub (a PUBLIC repo is simplest; `.env` is git-ignored).
2. In AWS Billing, create a **$5 budget alert**.
3. Use region **ap-south-1 (Mumbai)**.

## Option 1: Terraform (recommended)
1. Install Terraform and the AWS CLI. Create an IAM user with access keys (not the root account),
   then run `aws configure`.
2. Deploy:
   ```
   cd terraform
   terraform init
   terraform apply -var="repo_url=https://github.com/YOU/REPO.git"
   ```
3. Wait about 10 minutes, then open the `https_url` output.
4. Demo logins: `alice@bank.com` / `demo123` (account 123) and `bob@bank.com` / `demo123` (account 456).

## Option 2: AWS console only (no Terraform)
1. EC2 > Launch instance: Amazon Linux 2023, **t3.small**, 20 GB disk.
2. Security group: allow **HTTP (80)** from anywhere. No SSH needed.
3. Advanced details > User data: paste `user-data.sh` (edit the 3 variables at the top).
4. Wait ~5 minutes, open `http://<public IP>`.
5. Optional HTTPS: CloudFront > Create distribution > origin = the instance Public DNS, protocol HTTP only,
   cache policy CachingDisabled, origin request policy AllViewer, allow all HTTP methods.

## If the page does not load
EC2 console > select instance > Connect > Session Manager (Terraform option), then:
`sudo tail -n 50 /var/log/cloud-init-output.log` and `cd /opt/nexus && sudo docker compose -f docker-compose.prod.yml ps`.

## Before the interview
- Deploy **the day before** and test the HTTPS URL on your **company laptop and network**.
- Do the double-click test: send 100 from Alice to account 456 with a fast double-click; only one transfer appears.
- Take your slide 2 screenshots from this live site.

## After the interview (important)
`terraform destroy` (or terminate the EC2 instance and delete the CloudFront distribution), then confirm nothing is running in the EC2 console.

## Run locally
`docker compose up --build` (API on :8000), then `cd frontend && npm install && npm run dev`.

## Tests
`pip install -r requirements-dev.txt && pytest -v`
