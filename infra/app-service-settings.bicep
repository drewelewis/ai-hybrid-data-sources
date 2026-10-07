@description('Existing App Service name.')
param appServiceName string

@description('Private APIM gateway origin used by the application proxy.')
param apimOrigin string

@secure()
@description('Current App Service settings to preserve while adding template-managed values.')
param currentAppSettings object

resource appService 'Microsoft.Web/sites@2024-04-01' existing = {
  name: appServiceName
}

resource appSettings 'Microsoft.Web/sites/config@2024-04-01' = {
  parent: appService
  name: 'appsettings'
  properties: union(
    currentAppSettings,
    {
      APIM_ORIGIN: apimOrigin
      SCM_DO_BUILD_DURING_DEPLOYMENT: 'false'
    }
  )
}
