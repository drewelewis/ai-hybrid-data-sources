#requires -Version 7.0
[CmdletBinding()]
param(
    [string] $PolicyPath = 'peering\modules\apim-foundry-policy.xml'
)

$ErrorActionPreference = 'Stop'
[xml] $policy = Get-Content -Raw -LiteralPath $PolicyPath
$node = $policy.SelectSingleNode('/policies/outbound/choose/when/set-variable[@name="llmmgmt-model-safety"]')
if ($null -eq $node) { throw 'Missing upstream-model safety projection.' }
$expression = $node.GetAttribute('value')
if (-not $expression.StartsWith('@{') -or -not $expression.EndsWith('}')) {
    throw 'Expected a multi-statement safety projection.'
}
$body = $expression.Substring(2, $expression.Length - 3)
$className = 'ModelSafetyProbe' + [Guid]::NewGuid().ToString('N')
$source = @"
using System;
using System.Collections.Generic;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

public static class $className {
    public class Headers : Dictionary<string, string> {
        public Headers() : base(StringComparer.OrdinalIgnoreCase) {}
        public string GetValueOrDefault(string key, string fallback) {
            string value;
            return TryGetValue(key, out value) ? value : fallback;
        }
    }
    public class Body {
        public string Text;
        public int Reads;
        public bool Preserved = true;
        public T As<T>(bool preserveContent) {
            Reads++;
            Preserved = Preserved && preserveContent;
            return (T)(object)Text;
        }
    }
    public class Response {
        public Headers Headers = new Headers();
        public Body Body;
        public int StatusCode;
    }
    public class Context {
        public Response Response = new Response();
    }
    public static string Extract(Context context) {
        $body
    }
    public static string Run(string text, string contentType, int statusCode, string encoding, string length) {
        var context = new Context();
        context.Response.StatusCode = statusCode;
        context.Response.Headers["Content-Type"] = contentType;
        context.Response.Headers["Content-Encoding"] = encoding;
        context.Response.Headers["Content-Length"] = length;
        context.Response.Body = new Body { Text = text };
        var audit = JObject.Parse(Extract(context));
        audit["testBodyReads"] = context.Response.Body.Reads;
        audit["testPreserved"] = context.Response.Body.Preserved;
        audit["testBodyUnchanged"] = text == context.Response.Body.Text;
        audit["testStatusUnchanged"] = statusCode == context.Response.StatusCode;
        return JsonConvert.SerializeObject(audit);
    }
}
"@
$references = @(
    [Newtonsoft.Json.Linq.JObject].Assembly.Location
    Join-Path $PSHOME 'ref\System.Runtime.dll'
    Join-Path $PSHOME 'ref\System.Collections.dll'
    Join-Path $PSHOME 'ref\System.Linq.Expressions.dll'
    Join-Path $PSHOME 'ref\System.ComponentModel.TypeConverter.dll'
)
# PowerShell's bundled Newtonsoft targets an older, runtime-compatible System.Runtime.
Add-Type -TypeDefinition $source -ReferencedAssemblies $references -CompilerOptions @('/nowarn:1701', '/langversion:7.0')
$probe = $className -as [type]
$script:checks = 0
function Assert-Safety([bool] $Condition, [string] $Message) {
    if (-not $Condition) { throw $Message }
    $script:checks++
}
function Invoke-Safety(
    [string] $Json,
    [string] $ContentType = 'application/json',
    [int] $Status = 200,
    [string] $Encoding = '',
    [string] $Length = ''
) {
    $serialized = $probe::Run($Json, $ContentType, $Status, $Encoding, $Length)
    Assert-Safety (-not $serialized.Contains('MUST_NOT_LOG')) 'Raw model content or annotation detail leaked.'
    $result = $serialized | ConvertFrom-Json
    Assert-Safety ($result.testBodyUnchanged -and $result.testStatusUnchanged -and $result.testPreserved) 'Inspection changed the body/status or consumed content.'
    Assert-Safety ($result.source -eq 'upstream_model') 'Incorrect evidence provenance.'
    return $result
}

$blocked = Invoke-Safety -Status 400 -Json '{"error":{"code":"content_filter","message":"MUST_NOT_LOG_PROMPT","innererror":{"content_filter_result":{"violence":{"severity":"high","filtered":true},"self_harm":{"severity":"high","filtered":true},"jailbreak":{"detected":true,"filtered":true}}}}}'
Assert-Safety ($blocked.inspectionState -eq 'observed' -and $blocked.promptBlockReported) 'Structured prompt block not recognized.'
Assert-Safety ($blocked.results.Count -eq 3) 'Prompt categories lost.'
Assert-Safety (@($blocked.results | Where-Object { $_.stage -ne 'prompt' }).Count -eq 0) 'Incorrect prompt stage.'
foreach ($code in @('content_filter', 'content_policy_violation', 'ResponsibleAIPolicyViolation')) {
    $alternate = Invoke-Safety -Status 400 -Json ('{"code":"' + $code + '"}')
    Assert-Safety $alternate.promptBlockReported 'Existing API block-code contract not preserved.'
}
$innerCode = Invoke-Safety -Status 400 -Json '{"error":{"innererror":{"code":"ResponsibleAIPolicyViolation"}}}'
Assert-Safety $innerCode.promptBlockReported 'Inner model-block code not recognized.'
$non400 = Invoke-Safety -Status 500 -Json '{"error":{"code":"content_filter"}}'
Assert-Safety (-not $non400.promptBlockReported) 'Unrecognized HTTP/code combination reported as prompt block.'

$annotated = Invoke-Safety '{"prompt_filter_results":[{"prompt_index":0,"content_filter_results":{"violence":{"severity":"high","filtered":false}}}],"choices":[{"index":0,"finish_reason":"stop","message":{"content":"MUST_NOT_LOG_RESPONSE"},"content_filter_results":{"self_harm":{"severity":"safe","filtered":false}}}]}'
Assert-Safety ($annotated.inspectionState -eq 'observed' -and -not $annotated.promptBlockReported) 'Annotate-only risk must not be called a block.'
Assert-Safety ($annotated.results[0].severity -eq 'high' -and $annotated.results[0].filtered -eq $false) 'Annotate-only severity lost.'
Assert-Safety ($annotated.results[1].stage -eq 'completion') 'Completion annotations not distinguished.'

$completion = Invoke-Safety '{"choices":[{"index":0,"finish_reason":"content_filter","content_filter_results":{"self_harm":{"severity":"medium","filtered":true}}}]}'
Assert-Safety ($completion.completionFilterReported -and -not $completion.promptBlockReported) 'HTTP 200 completion filter not recognized.'
Assert-Safety ($completion.results[0].filtered) 'Filtered completion flag lost.'
$finishOnly = Invoke-Safety '{"choices":[{"finish_reason":"content_filter"}]}'
Assert-Safety ($finishOnly.inspectionState -eq 'observed' -and $finishOnly.completionFilterReported) 'Finish-reason-only evidence lost.'

$unrelated = Invoke-Safety -Status 400 -Json '{"error":{"code":"invalid_request","message":"content_filter MUST_NOT_LOG"}}'
Assert-Safety ($unrelated.inspectionState -eq 'no_annotations' -and -not $unrelated.promptBlockReported) 'HTTP status or error text was mistaken for safety evidence.'
$spoof = @{
    choices = @(@{ message = @{ content = '{"content_filter_results":{"violence":{"filtered":true}}} MUST_NOT_LOG' } })
} | ConvertTo-Json -Depth 8 -Compress
$noAnnotations = Invoke-Safety $spoof
Assert-Safety ($noAnnotations.inspectionState -eq 'no_annotations' -and $noAnnotations.results.Count -eq 0) 'Model text spoofed structured annotations.'

$stream = Invoke-Safety -Json 'data: MUST_NOT_LOG' -ContentType 'text/event-stream; charset=utf-8'
Assert-Safety ($stream.inspectionState -eq 'stream_not_inspected' -and $stream.testBodyReads -eq 0) 'Streaming body was read or reported as clean.'
$html = Invoke-Safety -Json 'MUST_NOT_LOG' -ContentType 'text/html'
Assert-Safety ($html.inspectionState -eq 'non_json_not_inspected' -and $html.testBodyReads -eq 0) 'Non-JSON body was inspected.'
$encoded = Invoke-Safety -Json 'MUST_NOT_LOG' -Encoding 'gzip'
Assert-Safety ($encoded.inspectionState -eq 'encoded_body_not_inspected' -and $encoded.testBodyReads -eq 0) 'Encoded body was inspected.'

$malformed = Invoke-Safety '{"MUST_NOT_LOG":'
Assert-Safety ($malformed.inspectionState -eq 'invalid_json') 'Malformed JSON not explicitly reported.'
$array = Invoke-Safety '[]'
Assert-Safety ($array.inspectionState -eq 'unsupported_json_shape') 'Unsupported JSON shape not explicit.'
$invalidAnnotation = Invoke-Safety '{"choices":[{"content_filter_results":{"violence":{"severity":"MUST_NOT_LOG","filtered":"true"}}}]}'
Assert-Safety ($invalidAnnotation.inspectionState -eq 'annotation_error' -and $invalidAnnotation.annotationErrors -gt 0) 'Invalid annotation types were accepted.'
$filterError = Invoke-Safety '{"choices":[{"content_filter_results":{"error":{"message":"MUST_NOT_LOG"}}}]}'
Assert-Safety ($filterError.inspectionState -eq 'annotation_error') 'Model annotation failure not reported.'
$nullFields = Invoke-Safety '{"choices":[{"content_filter_results":{"violence":{"severity":null,"filtered":null},"pii":{"detected":true,"filtered":null,"redacted":null}}}]}'
Assert-Safety ($nullFields.inspectionState -eq 'observed' -and $nullFields.annotationErrors -eq 0 -and $nullFields.results.Count -eq 1) 'Nullable optional fields were treated as filter failures.'

$oversize = Invoke-Safety -Json '{}' -Length '262145'
Assert-Safety ($oversize.inspectionState -eq 'oversize_not_inspected' -and $oversize.testBodyReads -eq 0) 'Declared size limit not enforced.'
$unknownLength = Invoke-Safety (' ' * 131073)
Assert-Safety ($unknownLength.inspectionState -eq 'oversize_not_inspected') 'Unknown-length parsing limit not enforced.'
$legacy = Invoke-Safety '{"prompt_annotations":[{"prompt_index":0,"content_filter_results":{"jailbreak":{"detected":true,"filtered":false}}}]}'
Assert-Safety ($legacy.results[0].detected -and -not $legacy.results[0].filtered) 'Legacy prompt annotations not recognized.'
$jsonType = Invoke-Safety -Json '{"choices":[{"finish_reason":"content_filter"}]}' -ContentType 'Application/JSON; charset=utf-8'
Assert-Safety $jsonType.completionFilterReported 'JSON content-type parameters/casing not handled.'
$details = Invoke-Safety '{"choices":[{"index":"MUST_NOT_LOG","content_filter_results":{"protected_material_code":{"detected":true,"filtered":false,"citation":{"URL":"MUST_NOT_LOG","license":"MUST_NOT_LOG"}},"pii":{"detected":true,"filtered":false,"redacted":true,"text":"MUST_NOT_LOG"}}}]}'
Assert-Safety ($details.results[0].index -eq -1 -and $details.results[1].redacted) 'Safe optional-model metadata lost.'

$large = @{
    prompt_filter_results = @(1..40 | ForEach-Object {
        @{ prompt_index = $_; content_filter_results = @{ violence = @{ severity = 'high'; filtered = $true } } }
    })
} | ConvertTo-Json -Depth 8 -Compress
$bounded = Invoke-Safety $large
Assert-Safety ($bounded.truncated -and $bounded.results.Count -eq 24 -and $bounded.inspectionState -eq 'observed_partial') 'Projection bounds not explicit.'
Assert-Safety (([Text.Encoding]::UTF8.GetByteCount(($bounded | ConvertTo-Json -Depth 8 -Compress))) -lt 8192) 'Safety metadata exceeds an Application Insights property limit.'

Write-Output "Validated actual APIM model-safety C# expression: $script:checks assertions."
