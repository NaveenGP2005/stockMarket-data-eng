# outputs.tf
output "eks_cluster_name" {
  value       = module.eks.cluster_name
  description = "The EKS Cluster Name"
}

output "eks_cluster_endpoint" {
  value       = module.eks.cluster_endpoint
  description = "The EKS Cluster Control Plane API endpoint"
}

output "ecr_repository_url" {
  value       = aws_ecr_repository.app_repo.repository_url
  description = "The URL of the ECR repository"
}
