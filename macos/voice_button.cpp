#include <chrono>
#include <charconv>
#include <cstdlib>
#include <cstring>
#include <launch.h>
#include <sys/socket.h>
#include <unistd.h>
#include <condition_variable>
#include <iostream>
#include <mutex>
#include <thread>
#include <pqrs/karabiner/driverkit/virtual_hid_device_driver.hpp>
#include <pqrs/karabiner/driverkit/virtual_hid_device_service.hpp>

namespace driver = pqrs::karabiner::driverkit::virtual_hid_device_driver;
namespace service = pqrs::karabiner::driverkit::virtual_hid_device_service;

int main(int argc, char **argv) {
  unsigned uid = 0, mask = 0, usage = 0;
  auto parse = [](const char *text, unsigned &value) {
    const auto *end = text + std::strlen(text);
    const auto result = std::from_chars(text, end, value);
    return result.ec == std::errc{} && result.ptr == end;
  };
  if (argc != 4 || !parse(argv[1], uid) || uid == 0 ||
      !parse(argv[2], mask) || mask > 255 ||
      !parse(argv[3], usage) || usage < 4 || usage > 231) {
    std::cerr << "Expected user ID, modifier mask and keyboard usage.\n";
    return 2;
  }
  int *descriptors = nullptr;
  size_t count = 0;
  if (launch_activate_socket("Button", &descriptors, &count) != 0 || count != 1) {
    std::free(descriptors);
    std::cerr << "VoiceLink requires its launchd socket.\n";
    return 1;
  }
  const int listener = descriptors[0];
  std::free(descriptors);
  using namespace std::chrono_literals;
  pqrs::dispatcher::extra::initialize_shared_dispatcher();
  {
    std::mutex mutex;
    std::condition_variable changed;
    bool ready = false;
    service::client keyboard;
    keyboard.connected.connect([&] {
      service::virtual_hid_keyboard_parameters parameters;
      parameters.set_country_code(pqrs::hid::country_code::us);
      keyboard.async_virtual_hid_keyboard_initialize(parameters);
    });
    keyboard.virtual_hid_keyboard_ready.connect([&](bool value) {
      std::lock_guard lock(mutex);
      ready = value;
      changed.notify_all();
    });
    keyboard.async_start();
    {
      std::unique_lock lock(mutex);
      if (!changed.wait_for(lock, 8s, [&] { return ready; })) {
        std::cerr << "Virtual keyboard did not become ready. Check the driver and daemon.\n";
        return 1;
      }
    }
    std::cerr << "VoiceLink virtual keyboard ready.\n";
    using namespace driver::hid_report;
    keyboard_input modifiers;
    for (unsigned bit = 1; bit <= 128; bit <<= 1)
      if (mask & bit)
        modifiers.modifiers.insert(static_cast<modifier>(bit));
    auto chord = modifiers;
    chord.keys.insert(usage);
    for (;;) {
      const int peer = accept(listener, nullptr, nullptr);
      if (peer < 0) {
        if (errno == EINTR)
          continue;
        break;
      }
      uid_t peer_uid = 0;
      gid_t peer_gid = 0;
      char command = 0;
      const timeval timeout{0, 250000};
      const bool allowed = getpeereid(peer, &peer_uid, &peer_gid) == 0 && peer_uid == uid &&
          setsockopt(peer, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof timeout) == 0 &&
          recv(peer, &command, 1, 0) == 1 && command == 'V';
      close(peer);
      if (!allowed)
        continue;
      {
        std::lock_guard lock(mutex);
        if (!ready)
          continue;
      }
      for (const auto &report : {modifiers, chord, modifiers, keyboard_input{}}) {
        keyboard.async_post_report(report);
        std::this_thread::sleep_for(60ms);
      }
    }
  }
  close(listener);
  pqrs::dispatcher::extra::terminate_shared_dispatcher();
}
