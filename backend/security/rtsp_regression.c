#include <gst/gst.h>
#include <gst/rtsp/gstrtspmessage.h>
#include <string.h>

int main(int argc, char **argv) {
    const char *headers[] = {
        "Digest realm= ", "Digest realm=  , nonce=\"test\"",
        "Digest realm=\t", "Digest realm=\r\n ",
        "Digest realm=\"test\", nonce=\"abc\"", "Basic realm=\"test\""
    };
    gst_init(&argc, &argv);
    for (guint i = 0; i < G_N_ELEMENTS(headers); ++i) {
        GstRTSPMessage message = {0};
        g_assert_cmpint(gst_rtsp_message_init_response(&message, GST_RTSP_STS_UNAUTHORIZED, NULL, NULL), ==, GST_RTSP_OK);
        g_assert_cmpint(gst_rtsp_message_add_header(&message, GST_RTSP_HDR_WWW_AUTHENTICATE, headers[i]), ==, GST_RTSP_OK);
        GstRTSPAuthCredential **credentials = gst_rtsp_message_parse_auth_credentials(&message, GST_RTSP_HDR_WWW_AUTHENTICATE);
        if (credentials) {
            for (guint j = 0; credentials[j]; ++j) {
                GstRTSPAuthParam **params = credentials[j]->params;
                if (params) for (guint k = 0; params[k]; ++k) {
                    g_assert_nonnull(params[k]->name);
                    g_assert_nonnull(params[k]->value);
                    g_assert_cmpuint(strlen(params[k]->value), <=, strlen(headers[i]));
                }
            }
            gst_rtsp_auth_credentials_free(credentials);
        }
        gst_rtsp_message_unset(&message);
    }
    g_print("{\"rtsp_digest_cases\":6,\"result\":\"PASS\"}\n");
    return 0;
}
