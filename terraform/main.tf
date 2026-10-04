
terraform {
  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 5.0" }
    random = { source = "hashicorp/random", version = "~> 3.5" }
  }
}

variable "region" {
  type    = string
  default = "ap-south-1" # Mumbai
}

variable "repo_url" {
  type        = string
  description = "Public GitHub URL of this project, e.g. https://github.com/nanda53/nexus.git"
}

variable "instance_type" {
  type    = string
  default = "t3.small" # 2 GB RAM: enough to build the React app
}

provider "aws" {
  region = var.region
}

data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

data "aws_vpc" "default" {
  default = true
}

resource "random_password" "db" {
  length  = 20
  special = false
}

resource "random_password" "jwt" {
  length  = 48
  special = false
}

resource "aws_security_group" "web" {
  name        = "nexus-web"
  description = "HTTP in, all out"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Lets you open a shell from the AWS console (Session Manager) with no SSH port
resource "aws_iam_role" "ssm" {
  name = "nexus-ssm"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.ssm.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ssm" {
  name = "nexus-ssm"
  role = aws_iam_role.ssm.name
}

resource "aws_instance" "nexus" {
  iam_instance_profile        = aws_iam_instance_profile.ssm.name
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = var.instance_type
  vpc_security_group_ids      = [aws_security_group.web.id]
  associate_public_ip_address = true

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  user_data = <<-EOT
    #!/bin/bash
    set -ex
    dnf install -y docker git
    systemctl enable --now docker
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -SL https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64 \
      -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    # small swap file so the frontend build never runs out of memory
    fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
    git clone ${var.repo_url} /opt/nexus
    cd /opt/nexus
    printf 'DB_PASSWORD=${random_password.db.result}\nSECRET_KEY=${random_password.jwt.result}\n' > .env
    docker compose -f docker-compose.prod.yml up -d --build
  EOT

  tags = { Name = "nexus-demo" }
}

# HTTPS front door. Caching is disabled so API calls always reach FastAPI.
resource "aws_cloudfront_distribution" "cdn" {
  enabled         = true
  comment         = "Nexus banking demo"
  price_class     = "PriceClass_All"
  is_ipv6_enabled = true

  origin {
    domain_name = aws_instance.nexus.public_dns
    origin_id   = "nexus-ec2"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id         = "nexus-ec2"
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods           = ["GET", "HEAD"]
    cache_policy_id          = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad" # Managed-CachingDisabled
    origin_request_policy_id = "216adef6-5c7f-47e4-b989-5492eafa07d3" # Managed-AllViewer
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

output "https_url" {
  value       = "https://${aws_cloudfront_distribution.cdn.domain_name}"
  description = "Use this one for the demo (HTTPS). Ready ~10 minutes after apply."
}

output "ec2_url" {
  value       = "http://${aws_instance.nexus.public_ip}"
  description = "Direct EC2 address (HTTP), useful for troubleshooting"
}
