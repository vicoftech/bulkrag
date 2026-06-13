terraform {
  backend "s3" {
    bucket         = "bulkrag-terraform-state-615216531593"
    key            = "ecs-extractor/prod/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "bulkrag-terraform-locks"
    encrypt        = true
  }
}
