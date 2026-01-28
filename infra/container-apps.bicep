// Azure Container Apps deployment with Container Registry
@description('Name of the Container Apps environment')
param environmentName string = 'skill-agent-env'

@description('Name of the Container App')
param containerAppName string = 'skill-agent-app'

@description('Name of the Container Registry')
param containerRegistryName string = 'skillagentreg${uniqueString(resourceGroup().id)}'

@description('Location for all resources')
param location string = resourceGroup().location

@description('Container image name')
param containerImage string = 'skill-agent:latest'

@description('CPU cores for the container')
param cpuCore string = '0.5'

@description('Memory size for the container')
param memorySize string = '1Gi'

@description('Minimum number of replicas')
param minReplicas int = 1

@description('Maximum number of replicas')
param maxReplicas int = 10

@description('Anthropic API Key')
@secure()
param anthropicApiKey string = ''

@description('OpenAI API Key')
@secure()
param openaiApiKey string = ''

@description('Google API Key')
@secure()
param googleApiKey string = ''

@description('GitHub repository URL for skills')
param githubRepoUrl string = ''

@description('Log Analytics Workspace Name')
param logAnalyticsWorkspaceName string = 'skill-agent-logs'

// Log Analytics Workspace
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Container Registry
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: containerRegistryName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

// Container Apps Environment
resource environment 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// Container App
resource containerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: containerAppName
  location: location
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        allowInsecure: false
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          username: containerRegistry.listCredentials().username
          passwordSecretRef: 'registry-password'
        }
      ]
      secrets: union(
        [
          {
            name: 'registry-password'
            value: containerRegistry.listCredentials().passwords[0].value
          }
        ],
        !empty(anthropicApiKey) ? [{ name: 'anthropic-api-key', value: anthropicApiKey }] : [],
        !empty(openaiApiKey) ? [{ name: 'openai-api-key', value: openaiApiKey }] : [],
        !empty(googleApiKey) ? [{ name: 'google-api-key', value: googleApiKey }] : []
      )
    }
    template: {
      containers: [
        {
          name: 'skill-agent'
          image: '${containerRegistry.properties.loginServer}/${containerImage}'
          resources: {
            cpu: json(cpuCore)
            memory: memorySize
          }
          env: union(
            !empty(anthropicApiKey) ? [{ name: 'ANTHROPIC_API_KEY', secretRef: 'anthropic-api-key' }] : [],
            !empty(openaiApiKey) ? [{ name: 'OPENAI_API_KEY', secretRef: 'openai-api-key' }] : [],
            !empty(googleApiKey) ? [{ name: 'GOOGLE_API_KEY', secretRef: 'google-api-key' }] : [],
            [
              {
                name: 'GITHUB_REPO_URL'
                value: githubRepoUrl
              }
              {
                name: 'APP_NAME'
                value: 'Skill Agent'
              }
              {
                name: 'LOG_LEVEL'
                value: 'INFO'
              }
            ]
          )
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 30
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '100'
              }
            }
          }
        ]
      }
    }
  }
}

// Outputs
output containerAppFQDN string = containerApp.properties.configuration.ingress.fqdn
output containerAppUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output containerRegistryLoginServer string = containerRegistry.properties.loginServer
output containerRegistryName string = containerRegistry.name
output environmentName string = environment.name
