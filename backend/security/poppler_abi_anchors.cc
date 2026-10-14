// Preserve vendor-exported libstdc++ objects that optimization otherwise drops.
// These are the real objects/types from the matching compiler headers, not stubs.
#include <algorithm>
#include <memory>
#include <typeinfo>

extern "C" {
__attribute__((used, visibility("default"))) const void *lms_poppler_abi_anchors[] = {
    &std::ranges::lower_bound,
    &std::ranges::find,
    &std::ranges::sort,
    &std::ranges::find_if,
    &typeid(std::_Sp_make_shared_tag),
};
}
