provider "aws" {
  region = "us-west-1"
}

# ==============================================================================
# Locals (Variables for consistency)
# ==============================================================================
locals {
  common_tags = {
    Project = "league_dudes"
    Owner   = "Andy"
  }
}

# ==============================================================================
# Data Sources
# ==============================================================================
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../backend" 
  output_path = "${path.module}/../deployment.zip" 
}

data "aws_secretsmanager_secret" "riot_dashboard_secret" {
  name = "prod/league-dudes/config" 
}

# ==============================================================================
# IAM Role & Permissions
# ==============================================================================
# 1. The Role (The Identity)
resource "aws_iam_role" "lambda_exec" {
  name = "league_lambda_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = local.common_tags
}

# 2. Inline Policy (DynamoDB + Logging)
resource "aws_iam_role_policy" "lambda_main_policy" {
  name = "league_lambda_main_policy"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:UpdateItem",
          "dynamodb:Scan"
        ]
        Resource = aws_dynamodb_table.league_matches.arn
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# 3. Secrets Policy (Separate Resource)
resource "aws_iam_policy" "lambda_secrets_policy" {
  name        = "league_dashboard_secrets_access"
  description = "Allow Lambda to read the Riot API key from Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "secretsmanager:GetSecretValue"
        Resource = data.aws_secretsmanager_secret.riot_dashboard_secret.arn
      }
    ]
  })
}

# 4. Attach Secrets Policy to Role
resource "aws_iam_role_policy_attachment" "attach_secrets_policy" {
  role       = aws_iam_role.lambda_exec.name  # FIXED: Was pointing to 'iam_for_lambda'
  policy_arn = aws_iam_policy.lambda_secrets_policy.arn
}

# ==============================================================================
# Database (DynamoDB)
# ==============================================================================
resource "aws_dynamodb_table" "league_matches" {
  name         = "LeagueMatches"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "matchId" 
  range_key    = "puuid"   

  attribute {
    name = "matchId"
    type = "S"
  }

  attribute {
    name = "puuid"
    type = "S"
  }

  tags = local.common_tags
}

# ==============================================================================
# Compute (Lambda Functions)
# ==============================================================================
# 1. The Poller Function
resource "aws_lambda_function" "league_poller" {
  function_name = "LeagueMatchPoller"
  
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  handler     = "lambda_function.lambda_handler"
  runtime     = "python3.9"
  role        = aws_iam_role.lambda_exec.arn
  timeout     = 60
  memory_size = 128

  environment {
    variables = {
      TABLE_NAME  = aws_dynamodb_table.league_matches.name
      SECRET_NAME = data.aws_secretsmanager_secret.riot_dashboard_secret.name
    }
  }

  tags = local.common_tags
}

# 2. The Reader Function
resource "aws_lambda_function" "league_dudes_reader" {
  function_name = "LeagueDudesReader"
  
  # Use the same zip file (it contains both scripts now)
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  handler     = "get_matches.lambda_handler" 
  runtime     = "python3.9"
  role        = aws_iam_role.lambda_exec.arn 
  timeout     = 10

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.league_matches.name
      MIN_GAME_DATE = "2026-01-16" # can change here or in AWS console
    }
  }

  tags = local.common_tags
}

# ==============================================================================
# EventBridge Scheduler (Automation)
# ==============================================================================

# 1. The Schedule Rule (The Timer)
resource "aws_cloudwatch_event_rule" "league_schedule" {
  name                = "league_dudes_matches_period_trigger"
  description         = "Triggers the League Match Poller every 20 minutes"
  
  # Cron expression or Rate expression
  schedule_expression = "rate(20 minutes)"
  
  tags = local.common_tags
}

# 2. The Target (Connects Timer -> Lambda)
resource "aws_cloudwatch_event_target" "trigger_lambda" {
  rule      = aws_cloudwatch_event_rule.league_schedule.name
  target_id = "TriggerLeagueLambda"
  arn       = aws_lambda_function.league_poller.arn
}

# 3. The Permission (Allows EventBridge to call Lambda)
resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.league_poller.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.league_schedule.arn
}

# ==============================================================================
# API Gateway (HTTP API)
# ==============================================================================
resource "aws_apigatewayv2_api" "league_dudes_api" {
  name          = "league_dudes_dashboard_api"
  protocol_type = "HTTP"
  
  cors_configuration {
    allow_origins = ["*"] 
    allow_methods = ["GET", "OPTIONS",]
    allow_headers = ["Content-Type"]
  }

  tags = local.common_tags
}

# Stage
resource "aws_apigatewayv2_stage" "league_dudes_default_stage" {
  api_id      = aws_apigatewayv2_api.league_dudes_api.id
  name        = "$default"
  auto_deploy = true
}

# Integration (Connects API Gateway -> Lambda)
resource "aws_apigatewayv2_integration" "league_dudes_reader_integration" {
  api_id           = aws_apigatewayv2_api.league_dudes_api.id
  integration_type = "AWS_PROXY"
  
  # Updated reference to the renamed lambda resource
  integration_uri    = aws_lambda_function.league_dudes_reader.invoke_arn
  integration_method = "POST" 
  payload_format_version = "2.0"
}

# Route (The URL path)
resource "aws_apigatewayv2_route" "league_dudes_get_matches" {
  api_id    = aws_apigatewayv2_api.league_dudes_api.id
  route_key = "GET /matches"
  
  # Updated reference to the renamed integration resource
  target    = "integrations/${aws_apigatewayv2_integration.league_dudes_reader_integration.id}"
}

# Permission (Allow API Gateway to call Lambda)
resource "aws_lambda_permission" "league_dudes_api_gw_permission" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  
  # Updated reference to the renamed lambda resource
  function_name = aws_lambda_function.league_dudes_reader.function_name
  principal     = "apigateway.amazonaws.com"
  
  # Updated reference to the renamed API resource
  source_arn    = "${aws_apigatewayv2_api.league_dudes_api.execution_arn}/*/*"
}


# ==============================================================================
# Frontend Hosting (S3)
# ==============================================================================

# 1. Create a Random Suffix (Ensures your bucket name is unique globally)
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# 2. The Bucket
resource "aws_s3_bucket" "frontend_bucket" {
  bucket = "league-dudes-dashboard-${random_id.bucket_suffix.hex}"
  
  tags = local.common_tags
}

# 3. Disable "Block Public Access" (Required for public websites)
resource "aws_s3_bucket_public_access_block" "public_access" {
  bucket = aws_s3_bucket.frontend_bucket.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# 4. Website Configuration (Tells S3 to treat this as a website)
resource "aws_s3_bucket_website_configuration" "website_config" {
  bucket = aws_s3_bucket.frontend_bucket.id

  index_document {
    suffix = "index.html"
  }
}

# 5. Bucket Policy (Allows the public internet to Read the files)
resource "aws_s3_bucket_policy" "allow_public_read" {
  bucket = aws_s3_bucket.frontend_bucket.id
  
  # Wait for the block settings to be disabled before applying this policy
  depends_on = [aws_s3_bucket_public_access_block.public_access]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.frontend_bucket.arn}/*"
      }
    ]
  })
}

# 6. Upload the HTML File automatically
resource "aws_s3_object" "index_html" {
  bucket       = aws_s3_bucket.frontend_bucket.id
  key          = "index.html"
  source       = "${path.module}/../frontend/index.html" 
  content_type = "text/html"
  
  # This hash triggers an upload only when you change the file content
  etag         = filemd5("${path.module}/../frontend/index.html")
}

# ==============================================================================
# Outputs
# ==============================================================================
output "dynamodb_table_arn" {
  value = aws_dynamodb_table.league_matches.arn
}

output "api_endpoint" {
  description = "The public URL for your API"
  # Updated reference
  value       = "${aws_apigatewayv2_api.league_dudes_api.api_endpoint}/matches"
}

output "dashboard_url" {
  description = "The URL for your TV Dashboard"
  value       = aws_s3_bucket_website_configuration.website_config.website_endpoint
}