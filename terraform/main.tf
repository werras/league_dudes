# Provider
provider "aws" {
  region = "us-west-1" 
}

# LeagueMatches DynamoDB Table
resource "aws_dynamodb_table" "league_matches" {
  name           = "LeagueMatches"
  billing_mode   = "PAY_PER_REQUEST" 

  # composite key
  hash_key       = "matchId" # Partition Key
  range_key      = "puuid" #sort key

  # attributes 
  attribute {
    name = "matchId"
    type = "S" #string
  }

  attribute {
    name = "puuid"
    type = "S"
  }

  tags = {
    Project = "league_dudes"
    Owner   = "Andy"
  }
}

# Output
output "dynamodb_table_arn" {
  value = aws_dynamodb_table.league_matches.arn
}