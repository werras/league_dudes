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
# Archive/zip lambda code
# ==============================================================================
data "archive_file" "lambda_zip" {
  type        = "zip"
  
  source_dir  = "${path.module}/../backend" 
  
  output_path = "${path.module}/../deployment.zip" 
}


# ==============================================================================
# Secrets Manager (Data Source)
# ==============================================================================
data "aws_secretsmanager_secret" "riot_dashboard_secret" {
  name = "prod/league-dudes/config" 
}

# ==============================================================================
# DynamoDB Tables
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
          "dynamodb:UpdateItem"
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
# Lambda Function
# ==============================================================================
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
# Outputs
# ==============================================================================
output "dynamodb_table_arn" {
  value = aws_dynamodb_table.league_matches.arn
}