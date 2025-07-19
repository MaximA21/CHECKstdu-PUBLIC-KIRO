# EventBridge Connection for ByteMe API
resource "aws_cloudwatch_event_connection" "byteme_connection" {
  name        = "${var.project_name}-${var.environment}-byteme-connection"
  description = "Connection for ByteMe provider API"

  authorization_type = "API_KEY"

  auth_parameters {
    api_key {
      key   = "X-Api-Key"
      value = var.byteme_api_key
    }
  }
}

resource "aws_cloudwatch_event_connection" "verbyndich_connection" {
  name        = "${var.project_name}-${var.environment}-verbyndich-connection"
  description = "Connection for Verbyndich provider API"

  authorization_type = "API_KEY"

  auth_parameters {
    api_key {
      key   = "X-Api-Key"
      value = "Servus"
    }
  }
}

# Servus Speed EventBridge Connection
resource "aws_cloudwatch_event_connection" "servus_speed_connection" {
  name        = "${var.project_name}-${var.environment}-servus-speed-connection"
  description = "Connection for Servus Speed provider API"

  authorization_type = "BASIC"

  auth_parameters {
    basic {
      username = "user_FE0AA56CF67F"   # Replace with actual username
      password = var.servus_speed_auth # Your basic auth password
    }
  }
}

resource "aws_cloudwatch_event_connection" "webwunder_connection" {
  name        = "${var.project_name}-${var.environment}-webwunder-connection"
  description = "Connection for WebWunder provider API"

  authorization_type = "API_KEY"

  auth_parameters {
    api_key {
      key   = "X-Api-Key"
      value = var.webwunder_api_key
    }
  }
}

resource "aws_cloudwatch_event_connection" "ping_perfect_connection" {
  name        = "${var.project_name}-${var.environment}-ping_perfect-connection"
  description = "Connection for Ping Perfect provider API"

  authorization_type = "API_KEY"

  auth_parameters {
    api_key {
      key   = "X-Api-Key"
      value = "Servus"
    }
  }
}

resource "aws_sfn_state_machine" "provider_workflow" {
  name     = "${var.project_name}-${var.environment}-provider-workflow"
  role_arn = aws_iam_role.step_functions_role.arn
  tracing_configuration {
    enabled = true
  }
  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.step_functions_logs.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }


  definition = <<EOF
{
  "Comment": "Multi-Provider Workflow - ByteMe + VerbynDich Parallel Processing",
  "StartAt": "ParallelProviders",
  "States": {
    "ParallelProviders": {
      "Type": "Parallel",
      "Branches": [
        {
          "StartAt": "CallByteMe",
          "States": {
            "CallByteMe": {
              "Type": "Task",
              "Resource": "arn:aws:states:::http:invoke",
              "Parameters": {
                "ApiEndpoint": "https://byteme.gendev7.check24.fun/app/api/products/data",
                "Method": "GET",
                "Authentication": {
                  "ConnectionArn": "${aws_cloudwatch_event_connection.byteme_connection.arn}"
                },
                "QueryParameters": {
                  "street.$": "$.address.street",
                  "houseNumber.$": "$.address.house_number",
                  "city.$": "$.address.city",
                  "plz.$": "$.address.postal_code"
                }
              },
              "ResultPath": "$.http_response",
              "Retry": [
                {
                  "ErrorEquals": ["States.Http.HttpException"],
                  "IntervalSeconds": 2,
                  "MaxAttempts": 3,
                  "BackoffRate": 2.0
                }
              ],
              "Catch": [
                {
                  "ErrorEquals": ["States.ALL"],
                  "Next": "SendByteMeFailure"
                }
              ],
              "Next": "SendByteMeSuccess"
            },
            "SendByteMeSuccess": {
              "Type": "Task",
              "Resource": "arn:aws:states:::sqs:sendMessage",
              "Parameters": {
                "QueueUrl": "${aws_sqs_queue.results_queue.url}",
                "MessageBody": {
                  "request_id.$": "$.request_id",
                  "connection_id.$": "$.connection_id",
                  "provider_name": "byteme",
                  "status": "success",
                  "raw_response.$": "$.http_response.ResponseBody",
                  "address.$": "$.address",
                  "share_token.$": "$.share_token"
                }
              },
              "End": true
            },
            "SendByteMeFailure": {
              "Type": "Task",
              "Resource": "arn:aws:states:::sqs:sendMessage",
              "Parameters": {
                "QueueUrl": "${aws_sqs_queue.results_queue.url}",
                "MessageBody": {
                  "request_id.$": "$.request_id",
                  "connection_id.$": "$.connection_id",
                  "provider_name": "byteme",
                  "status": "failed",
                  "error_details.$": "$.Error",
                  "address.$": "$.address",
                  "share_token.$": "$.share_token"
                }
              },
              "End": true
            }
          }
        },
        {
          "StartAt": "PrepareVerbynDichPages",
          "States": {
            "PrepareVerbynDichPages": {
              "Type": "Pass",
              "Comment": "Generate array of page numbers 0-19 for parallel processing",
              "Result": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17],
              "ResultPath": "$.page_numbers",
              "Next": "VerbynDichParallelFetch"
            },
            "VerbynDichParallelFetch": {
              "Type": "Map",
              "Comment": "Fetch all VerbynDich pages in parallel with fault tolerance",
              "MaxConcurrency": 6,
              "ItemsPath": "$.page_numbers",
              "ResultPath": "$.page_results",
           "Parameters": {
  "page_number.$": "$$.Map.Item.Value",
  "address.$": "$.address"
},
              "Iterator": {
                "StartAt": "CallVerbynDichSinglePage",
                "States": {
                  "CallVerbynDichSinglePage": {
                    "Type": "Task",
                    "Resource": "arn:aws:states:::http:invoke",
                    "Parameters": {
                      "ApiEndpoint": "https://verbyndich.gendev7.check24.fun/check24/data",
                      "Method": "POST",
                      "Headers": {
                        "Content-Type": "text/plain"
                      },
                      "Authentication": {
                        "ConnectionArn": "${aws_cloudwatch_event_connection.verbyndich_connection.arn}"
                      },
                      "QueryParameters": {
                        "apiKey": "${var.verbyndich_api_key}",
                        "page.$": "States.Format('{}', $.page_number)"
                      },
                      "RequestBody.$": "States.Format('{};{};{};{}', $.address.street, $.address.house_number, $.address.city, $.address.postal_code)"
                    },
                    "ResultPath": "$.api_response",
                    "Retry": [
                      {
                        "ErrorEquals": ["States.Http.HttpException"],
                        "IntervalSeconds": 2,
                        "MaxAttempts": 3,
                        "BackoffRate": 2.0
                      },
                      {
                        "ErrorEquals": ["States.Http.StatusCode.429"],
                        "IntervalSeconds": 5,
                        "MaxAttempts": 2,
                        "BackoffRate": 3.0
                      }
                    ],
                    "Catch": [
                      {
                        "ErrorEquals": ["States.ALL"],
                        "ResultPath": "$.error_info",
                        "Next": "HandlePageError"
                      }
                    ],
                    "Next": "ProcessPageResponse"
                  },
                  "ProcessPageResponse": {
                    "Type": "Pass",
                    "Comment": "Add page metadata and return response",
                    "Parameters": {
                      "page_number.$": "$.page_number",
                      "success": true,
                      "response_data.$": "$.api_response.ResponseBody",
                      "error_info": null
                    },
                    "End": true
                  },
                  "HandlePageError": {
                    "Type": "Pass",
                    "Comment": "Return error info but don't fail the entire map operation",
                    "Parameters": {
                      "page_number.$": "$.page_number",
                      "success": false,
                      "response_data": null,
                      "error_info.$": "$.error_info"
                    },
                    "End": true
                  }
                }
              },
              "Catch": [
                {
                  "ErrorEquals": ["States.ALL"],
                  "Next": "SendVerbynDichTotalFailure"
                }
              ],
              "Next": "ProcessVerbynDichResults"
            },
            "ProcessVerbynDichResults": {
              "Type": "Pass",
              "Comment": "Filter and aggregate successful responses, preserve original context",
              "Parameters": {
                "request_id.$": "$.request_id",
                "connection_id.$": "$.connection_id",
                "address.$": "$.address",
                "share_token.$": "$.share_token",
                "successful_pages.$": "$.page_results[?(@.success == true)]",
                "failed_pages.$": "$.page_results[?(@.success == false)]",
                "valid_offers.$": "$.page_results[?(@.success == true && @.response_data.valid == true)].response_data",
                "total_pages_attempted": 20,
                "successful_page_count.$": "States.ArrayLength($.page_results[?(@.success == true)])",
                "failed_page_count.$": "States.ArrayLength($.page_results[?(@.success == false)])"
              },
              "Next": "SendVerbynDichAggregatedResults"
            },
            "SendVerbynDichAggregatedResults": {
              "Type": "Task",
              "Resource": "arn:aws:states:::sqs:sendMessage",
              "Parameters": {
                "QueueUrl": "${aws_sqs_queue.results_queue.url}",
                "MessageBody": {
                  "request_id.$": "$.request_id",
                  "connection_id.$": "$.connection_id",
                  "provider_name": "verbyndich",
                  "status": "success",
                  "raw_response.$": "$.valid_offers",
                  "metadata": {
                    "total_pages_attempted.$": "$.total_pages_attempted",
                    "successful_pages.$": "$.successful_page_count",
                    "failed_pages.$": "$.failed_page_count",
                    "processing_method": "parallel_with_fault_tolerance"
                  },
                  "address.$": "$.address",
                  "share_token.$": "$.share_token"
                }
              },
              "End": true
            },
            "SendVerbynDichTotalFailure": {
              "Type": "Task",
              "Resource": "arn:aws:states:::sqs:sendMessage",
              "Parameters": {
                "QueueUrl": "${aws_sqs_queue.results_queue.url}",
                "MessageBody": {
                  "request_id.$": "$.request_id",
                  "connection_id.$": "$.connection_id",
                  "provider_name": "verbyndich",
                  "status": "failed",
                  "error_details": "Complete failure in parallel processing",
                  "address.$": "$.address",
                  "share_token.$": "$.share_token"
                }
              },
              "End": true
            }
          }
        },
{
  "StartAt": "CallServusSpeedAvailableProducts",
  "States": {
    "CallServusSpeedAvailableProducts": {
      "Type": "Task",
      "Resource": "arn:aws:states:::http:invoke",
      "Parameters": {
        "ApiEndpoint": "https://servus-speed.gendev7.check24.fun/api/external/available-products",
        "Method": "POST",
        "Headers": {
          "Content-Type": "application/json"
        },
        "Authentication": {
          "ConnectionArn": "${aws_cloudwatch_event_connection.servus_speed_connection.arn}"
        },
        "RequestBody": {
          "address": {
            "strasse.$": "$.address.street",
            "hausnummer.$": "$.address.house_number",
            "postleitzahl.$": "$.address.postal_code",
            "stadt.$": "$.address.city",
            "land": "DE"
          }
        }
      },
      "ResultPath": "$.products_response",
      "Retry": [
        {
          "ErrorEquals": ["States.Http.HttpException"],
          "IntervalSeconds": 2,
          "MaxAttempts": 3,
          "BackoffRate": 2.0
        },
 {
          "ErrorEquals": ["States.Http.StatusCode.503"],
          "IntervalSeconds": 5,
          "MaxAttempts": 3,
          "BackoffRate": 2.0
        }
      ],
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
  "ResultPath": "$.error_details",
          "Next": "SendServusSpeedFailure"
        }
      ],
      "Next": "ServusSpeedParallelDetails"
    },
    "ServusSpeedParallelDetails": {
      "Type": "Map",
      "Comment": "Fetch product details for all available products in parallel",
      "MaxConcurrency": 5,
      "ItemsPath": "$.products_response.ResponseBody.availableProducts",
"Parameters": {
"product_id.$": "$$.Map.Item.Value",
"address.$": "$.address"
},
      "ResultPath": "$.product_details",
      "Iterator": {
        "StartAt": "CallProductDetails",
        "States": {
          "CallProductDetails": {
            "Type": "Task",
            "Resource": "arn:aws:states:::http:invoke",
            "Parameters": {
              "ApiEndpoint.$": "States.Format('https://servus-speed.gendev7.check24.fun/api/external/product-details/{}', $.product_id)",
              "Method": "POST",
              "Headers": {
                "Content-Type": "application/json"
              },
              "Authentication": {
                "ConnectionArn": "${aws_cloudwatch_event_connection.servus_speed_connection.arn}"
              },
   "RequestBody": {
                "address": {
                  "strasse.$": "$.address.street",
                  "hausnummer.$": "$.address.house_number",
                  "postleitzahl.$": "$.address.postal_code",
                  "stadt.$": "$.address.city",
                  "land": "DE"
                }
              }
            },
            "ResultPath": "$.api_response",
            "Retry": [
              {
                "ErrorEquals": ["States.Http.HttpException"],
                "IntervalSeconds": 1,
                "MaxAttempts": 2,
                "BackoffRate": 2.0
              }
            ],
            "Catch": [
              {
                "ErrorEquals": ["States.ALL"],
                "Next": "HandleProductDetailError"
              }
            ],
            "Next": "ProcessProductDetail"
          },
          "ProcessProductDetail": {
            "Type": "Pass",
            "Comment": "Add product metadata and return response",
            "Parameters": {
              "product_id.$": "$",
              "success": true,
              "product_data.$": "$.api_response.ResponseBody",
              "error_info": null
            },
            "End": true
          },
          "HandleProductDetailError": {
            "Type": "Pass",
            "Comment": "Return error info but don't fail the entire map operation",
            "Parameters": {
              "product_id.$": "$",
              "success": false,
              "product_data": null
            },
            "End": true
          }
        }
      },
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "Next": "SendServusSpeedFailure"
        }
      ],
      "Next": "ProcessServusSpeedResults"
    },
    "ProcessServusSpeedResults": {
      "Type": "Pass",
      "Comment": "Filter and aggregate successful product details",
      "Parameters": {
"request_id.$": "$.request_id",
                "connection_id.$": "$.connection_id",
 "address.$": "$.address",
                "share_token.$": "$.share_token",
        "successful_products.$": "$.product_details[?(@.success == true)]",
        "failed_products.$": "$.product_details[?(@.success == false)]",
        "valid_products.$": "$.product_details[?(@.success == true)].product_data",
        "total_products_attempted.$": "States.ArrayLength($.products_response.ResponseBody.availableProducts)",
        "successful_product_count.$": "States.ArrayLength($.product_details[?(@.success == true)])",
        "failed_product_count.$": "States.ArrayLength($.product_details[?(@.success == false)])"
      },
      "Next": "SendServusSpeedSuccess"
    },
    "SendServusSpeedSuccess": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sqs:sendMessage",
      "Parameters": {
        "QueueUrl": "${aws_sqs_queue.results_queue.url}",
        "MessageBody": {
          "request_id.$": "$.request_id",
          "connection_id.$": "$.connection_id",
          "provider_name": "servus_speed",
          "status": "success",
          "raw_response.$": "$.valid_products",
          "metadata": {
            "total_products_attempted.$": "$.total_products_attempted",
            "successful_products.$": "$.successful_product_count",
            "failed_products.$": "$.failed_product_count",
            "processing_method": "two_step_parallel"
          },
          "address.$": "$.address",
          "share_token.$": "$.share_token"
        }
      },
      "End": true
    },
    "SendServusSpeedFailure": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sqs:sendMessage",
      "Parameters": {
        "QueueUrl": "${aws_sqs_queue.results_queue.url}",
        "MessageBody": {
          "request_id.$": "$.request_id",
          "connection_id.$": "$.connection_id",
          "provider_name": "servus_speed",
          "status": "failed",
          "error_details": "Failed to get available products or product details",
          "address.$": "$.address",
          "share_token.$": "$.share_token"
        }
      },
      "End": true
    }
  }
},
      {
  "StartAt": "NormalizeAddressForWebWunder",
  "States": {
    "NormalizeAddressForWebWunder": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "${aws_lambda_function.address_normalizer.function_name}",
        "Payload": {
          "request_id.$": "$.request_id",
          "connection_id.$": "$.connection_id",
          "share_token.$": "$.share_token",
          "address.$": "$.address"
        }
      },
      "ResultPath": "$.normalization_result",
      "Next": "ExtractNormalizedData"
    },
    "ExtractNormalizedData": {
      "Type": "Pass",
      "Comment": "Extract normalized data from Lambda response",
      "Parameters": {
        "request_id.$": "$.normalization_result.Payload.request_id",
        "connection_id.$": "$.normalization_result.Payload.connection_id",
        "share_token.$": "$.normalization_result.Payload.share_token",
        "address.$": "$.normalization_result.Payload.address",
        "normalized_address.$": "$.normalization_result.Payload.normalized_address",
        "connection_types.$": "$.normalization_result.Payload.connection_types"
      },
      "Next": "WebWunderParallelFetch"
    },
    "WebWunderParallelFetch": {
      "Type": "Map",
      "Comment": "Fetch all WebWunder connection types in parallel",
      "MaxConcurrency": 3,
      "ItemsPath": "$.connection_types",
      "ResultPath": "$.connection_results",
      "Parameters": {
        "connection_type.$": "$$.Map.Item.Value",
        "request_id.$": "$.request_id",
        "connection_id.$": "$.connection_id",
        "share_token.$": "$.share_token",
        "address.$": "$.address",
        "normalized_address.$": "$.normalized_address"
      },
      "Iterator": {
        "StartAt": "CallWebWunderConnectionType",
        "States": {
          "CallWebWunderConnectionType": {
            "Type": "Task",
            "Resource": "arn:aws:states:::http:invoke",
            "Parameters": {
              "ApiEndpoint": "https://webwunder.gendev7.check24.fun/endpunkte/soap/ws/getInternetOffers.wsdl",
              "Method": "POST",
              "Headers": {
                "Content-Type": "text/xml; charset=utf-8"
              },
              "Authentication": {
                "ConnectionArn": "${aws_cloudwatch_event_connection.webwunder_connection.arn}"
              },
              "RequestBody.$": "States.Format('<soapenv:Envelope xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\" xmlns:gs=\"http://webwunder.gendev7.check24.fun/offerservice\"><soapenv:Header/><soapenv:Body><gs:legacyGetInternetOffers><gs:input><gs:installation>true</gs:installation><gs:connectionEnum>{}</gs:connectionEnum><gs:address><gs:street>{}</gs:street><gs:houseNumber>{}</gs:houseNumber><gs:city>{}</gs:city><gs:plz>{}</gs:plz><gs:countryCode>DE</gs:countryCode></gs:address></gs:input></gs:legacyGetInternetOffers></soapenv:Body></soapenv:Envelope>', $.connection_type, $.normalized_address.street, $.normalized_address.house_number, $.normalized_address.city, $.normalized_address.postal_code)"
            },
            "ResultPath": "$.api_response",
            "Retry": [
              {
                "ErrorEquals": ["States.Http.HttpException"],
                "IntervalSeconds": 2,
                "MaxAttempts": 3,
                "BackoffRate": 2.0
              }
            ],
            "Catch": [
              {
                "ErrorEquals": ["States.ALL"],
                "ResultPath": "$.error_info",
                "Next": "HandleConnectionError"
              }
            ],
            "Next": "ProcessConnectionResponse"
          },
          "ProcessConnectionResponse": {
            "Type": "Choice",
            "Choices": [
              {
                "And": [
                  {
                    "Variable": "$.api_response.StatusCode",
                    "NumericEquals": 200
                  },
                  {
                    "Or": [
                      {
                        "Variable": "$.api_response.ResponseBody",
                        "StringMatches": "*<ns2:products>*"
                      },
                      {
                        "Variable": "$.api_response.ResponseBody",
                        "StringMatches": "*<products>*"
                      }
                    ]
                  }
                ],
                "Next": "HandleConnectionSuccess"
              }
            ],
            "Default": "HandleConnectionError"
          },
          "HandleConnectionSuccess": {
            "Type": "Pass",
            "Parameters": {
              "connection_type.$": "$.connection_type",
              "success": true,
              "response_data.$": "$.api_response.ResponseBody",
              "status_code.$": "$.api_response.StatusCode"
            },
            "End": true
          },
          "HandleConnectionError": {
            "Type": "Pass",
            "Parameters": {
              "connection_type.$": "$.connection_type",
              "success": false,
              "response_data": null,
              "error_info.$": "$.error_info"
            },
            "End": true
          }
        }
      },
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "Next": "SendWebWunderTotalFailure"
        }
      ],
      "Next": "ProcessWebWunderResults"
    },
    "ProcessWebWunderResults": {
      "Type": "Pass",
      "Parameters": {
        "request_id.$": "$.request_id",
        "connection_id.$": "$.connection_id",
        "address.$": "$.address",
        "share_token.$": "$.share_token",
        "successful_connections.$": "$.connection_results[?(@.success == true)]",
        "connection_types_attempted": 3,
        "successful_connection_count.$": "States.ArrayLength($.connection_results[?(@.success == true)])"
      },
      "Next": "SendWebWunderAggregatedResults"
    },
    "SendWebWunderAggregatedResults": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sqs:sendMessage",
      "Parameters": {
        "QueueUrl": "${aws_sqs_queue.results_queue.url}",
        "MessageBody": {
          "request_id.$": "$.request_id",
          "connection_id.$": "$.connection_id",
          "provider_name": "webwunder",
          "status": "success",
          "raw_response.$": "$.successful_connections",
          "metadata": {
            "connection_types_attempted.$": "$.connection_types_attempted",
            "successful_connections.$": "$.successful_connection_count",
            "processing_method": "parallel_connection_types"
          },
          "address.$": "$.address",
          "share_token.$": "$.share_token"
        }
      },
      "End": true
    },
    "SendWebWunderTotalFailure": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sqs:sendMessage",
      "Parameters": {
        "QueueUrl": "${aws_sqs_queue.results_queue.url}",
        "MessageBody": {
          "request_id.$": "$.request_id",
          "connection_id.$": "$.connection_id",
          "provider_name": "webwunder",
          "status": "failed",
          "error_details": "Complete failure in parallel connection type processing",
          "address.$": "$.address",
          "share_token.$": "$.share_token"
        }
      },
      "End": true
    }
  }
},

{
  "StartAt": "PreparePingPerfectCalls",
  "States": {
    "PreparePingPerfectCalls": {
      "Type": "Pass",
      "Comment": "Prepare fiber and non-fiber calls for parallel processing",
      "Parameters": {
        "request_id.$": "$.request_id",
        "connection_id.$": "$.connection_id",
        "share_token.$": "$.share_token",
        "address.$": "$.address",
        "call_types": [
          {"wants_fiber": true, "type": "fiber"},
          {"wants_fiber": false, "type": "dsl_cable"}
        ]
      },
      "Next": "PingPerfectParallelFetch"
    },
    "PingPerfectParallelFetch": {
      "Type": "Map",
      "Comment": "Generate signatures and call Ping Perfect API for fiber and non-fiber in parallel",
      "MaxConcurrency": 2,
      "ItemsPath": "$.call_types",
      "ResultPath": "$.call_results",
      "Parameters": {
        "call_info.$": "$$.Map.Item.Value",
        "request_id.$": "$.request_id",
        "connection_id.$": "$.connection_id",
        "share_token.$": "$.share_token",
        "address.$": "$.address"
      },
      "Iterator": {
        "StartAt": "GeneratePingPerfectSignature",
        "States": {
          "GeneratePingPerfectSignature": {
            "Type": "Task",
            "Resource": "arn:aws:states:::lambda:invoke",
            "Parameters": {
              "FunctionName": "${aws_lambda_function.ping_perfect_signer.function_name}",
              "Payload": {
                "request_id.$": "$.request_id",
                "connection_id.$": "$.connection_id",
                "share_token.$": "$.share_token",
                "address.$": "$.address",
                "wants_fiber.$": "$.call_info.wants_fiber"
              }
            },
            "ResultPath": "$.signature_response",
            "Retry": [
              {
                "ErrorEquals": ["Lambda.ServiceException", "Lambda.AWSLambdaException"],
                "IntervalSeconds": 2,
                "MaxAttempts": 3,
                "BackoffRate": 2.0
              }
            ],
            "Catch": [
              {
                "ErrorEquals": ["States.ALL"],
                "ResultPath": "$.error_info",
                "Next": "HandleSignatureError"
              }
            ],
            "Next": "CheckSignatureGeneration"
          },
          "CheckSignatureGeneration": {
            "Type": "Choice",
            "Choices": [
              {
                "Variable": "$.signature_response.Payload.success",
                "BooleanEquals": true,
                "Next": "CallPingPerfectAPI"
              }
            ],
            "Default": "HandleSignatureError"
          },
          "CallPingPerfectAPI": {
            "Type": "Task",
            "Resource": "arn:aws:states:::http:invoke",
            "Parameters": {
              "ApiEndpoint.$": "$.signature_response.Payload.api_endpoint",
              "Method": "POST",
              "Headers": {
                "Content-Type": "application/json",
                "X-Signature.$": "$.signature_response.Payload.signature",
                "X-Timestamp.$": "$.signature_response.Payload.timestamp",
                "X-Client-Id.$": "$.signature_response.Payload.client_id"
              },
              "Authentication": {
                "ConnectionArn": "${aws_cloudwatch_event_connection.ping_perfect_connection.arn}"
              },
              "RequestBody.$": "$.signature_response.Payload.request_body"
            },
            "ResultPath": "$.api_response",
            "Retry": [
              {
                "ErrorEquals": ["States.Http.HttpException"],
                "IntervalSeconds": 2,
                "MaxAttempts": 3,
                "BackoffRate": 2.0
              }
            ],
            "Catch": [
              {
                "ErrorEquals": ["States.ALL"],
                "ResultPath": "$.error_info",
                "Next": "HandleAPIError"
              }
            ],
            "Next": "ProcessAPIResponse"
          },
          "ProcessAPIResponse": {
            "Type": "Choice",
            "Choices": [
              {
                "Variable": "$.api_response.StatusCode",
                "NumericEquals": 200,
                "Next": "HandleAPISuccess"
              }
            ],
            "Default": "HandleAPIError"
          },
          "HandleAPISuccess": {
            "Type": "Pass",
            "Comment": "Add call metadata and return successful response",
            "Parameters": {
              "call_type.$": "$.call_info.type",
              "wants_fiber.$": "$.call_info.wants_fiber",
              "success": true,
              "offers.$": "$.api_response.ResponseBody",
              "status_code.$": "$.api_response.StatusCode",
              "error_info": null
            },
            "End": true
          },
          "HandleAPIError": {
            "Type": "Pass",
            "Comment": "Return API error info",
            "Parameters": {
              "call_type.$": "$.call_info.type",
              "wants_fiber.$": "$.call_info.wants_fiber",
              "success": false,
              "offers": [],
              "error_info": "Ping Perfect API call failed",
              "status_code.$": "$.api_response.StatusCode"
            },
            "End": true
          },
          "HandleSignatureError": {
            "Type": "Pass",
            "Comment": "Return signature generation error",
            "Parameters": {
              "call_type.$": "$.call_info.type",
              "wants_fiber.$": "$.call_info.wants_fiber",
              "success": false,
              "offers": [],
              "error_info": "Signature generation failed"
            },
            "End": true
          }
        }
      },
      "Catch": [
        {
          "ErrorEquals": ["States.ALL"],
          "Next": "SendPingPerfectTotalFailure"
        }
      ],
      "Next": "ProcessPingPerfectResults"
    },
    "ProcessPingPerfectResults": {
      "Type": "Pass",
      "Comment": "Filter and aggregate successful call responses",
      "Parameters": {
        "request_id.$": "$.request_id",
        "connection_id.$": "$.connection_id",
        "address.$": "$.address",
        "share_token.$": "$.share_token",
        "successful_calls.$": "$.call_results[?(@.success == true)]",
        "failed_calls.$": "$.call_results[?(@.success == false)]",
        "call_results.$": "$.call_results",
        "call_types_attempted": 2,
        "successful_call_count.$": "States.ArrayLength($.call_results[?(@.success == true)])",
        "failed_call_count.$": "States.ArrayLength($.call_results[?(@.success == false)])"
      },
      "Next": "SendPingPerfectAggregatedResults"
    },
    "SendPingPerfectAggregatedResults": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sqs:sendMessage",
      "Parameters": {
        "QueueUrl": "${aws_sqs_queue.results_queue.url}",
        "MessageBody": {
          "request_id.$": "$.request_id",
          "connection_id.$": "$.connection_id",
          "provider_name": "ping_perfect",
          "status": "success",
          "raw_response.$": "$.successful_calls",
          "metadata": {
            "call_types_attempted.$": "$.call_types_attempted",
            "successful_calls.$": "$.successful_call_count",
            "failed_calls.$": "$.failed_call_count",
            "call_details.$": "$.call_results",
            "processing_method": "parallel_signed_calls"
          },
          "address.$": "$.address",
          "share_token.$": "$.share_token"
        }
      },
      "End": true
    },
    "SendPingPerfectTotalFailure": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sqs:sendMessage",
      "Parameters": {
        "QueueUrl": "${aws_sqs_queue.results_queue.url}",
        "MessageBody": {
          "request_id.$": "$.request_id",
          "connection_id.$": "$.connection_id",
          "provider_name": "ping_perfect",
          "status": "failed",
          "error_details": "Complete failure in parallel signature/API processing",
          "address.$": "$.address",
          "share_token.$": "$.share_token"
        }
      },
      "End": true
    }
  }
}
 ],
      "End": true
    }
  }
}
EOF



  tags = {
    Name        = "${var.project_name}-provider-workflow"
    Environment = var.environment
  }
}

# IAM-Rolle für Step Functions
resource "aws_iam_role" "step_functions_role" {
  name = "${var.project_name}-${var.environment}-step-functions-role"

  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-step-functions-role"
    Environment = var.environment
  }
}

# IAM-Policy für Step Functions
resource "aws_iam_policy" "step_functions_policy" {
  name        = "${var.project_name}-${var.environment}-step-functions-policy"
  description = "Policy for Step Functions state machine"

  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage"
        ]
        Resource = [
          aws_sqs_queue.results_queue.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "states:InvokeHTTPEndpoint"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "events:RetrieveConnectionCredentials"
        ]
        Resource = [
          aws_cloudwatch_event_connection.byteme_connection.arn,
          aws_cloudwatch_event_connection.verbyndich_connection.arn,
          aws_cloudwatch_event_connection.servus_speed_connection.arn,
          aws_cloudwatch_event_connection.webwunder_connection.arn,
          aws_cloudwatch_event_connection.ping_perfect_connection.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:*:secret:events!connection/*"
      },
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "${aws_cloudwatch_log_group.step_functions_logs.arn}:*"
      },
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = aws_lambda_function.address_normalizer.arn
      },
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = aws_lambda_function.ping_perfect_signer.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "step_functions_policy_attachment" {
  role       = aws_iam_role.step_functions_role.name
  policy_arn = aws_iam_policy.step_functions_policy.arn
}

# Add CloudWatch Log Group FIRST
resource "aws_cloudwatch_log_group" "step_functions_logs" {
  name              = "/aws/stepfunctions/${var.project_name}-${var.environment}-provider-workflow"
  retention_in_days = 7

  tags = {
    Name        = "${var.project_name}-step-functions-logs"
    Environment = var.environment
  }
}