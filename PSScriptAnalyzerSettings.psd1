@{
    Severity     = @('Error', 'Warning')
    ExcludeRules = @(
        # Build and check scripts are console tools; Write-Host is the intended output channel.
        'PSAvoidUsingWriteHost'
    )
}
