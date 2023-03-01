import importlib
import logging
import pkgutil
import signal
import sys
from multiprocessing import Process

import igibson
import igibson.examples as examples
from igibson.utils.utils import let_user_pick

TIMEOUT = 4


def interrupted(signum, frame):
    raise ValueError("Time-up for keyboard input")


signal.signal(signal.SIGALRM, interrupted)


def timed_input(example_name):
    try:
        print("Next example: " + example_name)
        input("Press ENTER to skip or wait 4 secs to execute\n")
        return True
    except ValueError:
        # timeout
        return False


def main():
    """
    Selector tool to see all available examples and pick one to run (in interactive or test mode), get more information,
    or run all examples one after the other
    """
    examples_list = ["help", "all", "quit", "switch to test mode"]
    for kk in pkgutil.walk_packages(examples.__path__, examples.__name__ + "."):
        # Exclude package files, the example_selector itself
        if not kk.ispkg and kk.name[17:] != "example_selector":
            examples_list += [kk.name[17:]]

    selected_demo = 0
    excluded_examples = ["_ui", "vr_"]
    test_mode = "user"
    while selected_demo == 0 or selected_demo == 3:
        print(igibson.__logo__)
        print(
            "Select a demo/example, 'help' for information about a specific demo, 'all' to run all demos, or 'test' "
            "to toggle on the test-only mode:"
        )
        selected_demo = let_user_pick(examples_list, print_intro=False) - 1
        if selected_demo == 0:
            user_input = input("\nProvide the number of the example you need information for: ")
            if not user_input.isdigit():
                continue
            else:
                help_demo = int(user_input) - 1
            if help_demo == 0:
                print("Print the description of a demo/example")
            elif help_demo == 1:
                print("Execute all demos/examples in order")
            elif help_demo == 2:
                print("Quit the exampler")
            elif help_demo == 3:
                print("Toggle the test mode to execute examples (short, headless versions)")
            else:
                module_help = importlib.import_module("igibson.examples." + examples_list[help_demo])
                print(module_help.main.__doc__)
            input("Press enter")
        elif selected_demo == 1:
            print("Executing all demos " + ["in interactive mode", "in test mode"][test_mode == "random"])
            for idx in range(4, len(examples_list)):
                if not any(excluded_example in examples_list[selected_demo] for excluded_example in excluded_examples):
                    print("*" * 80)
                    print("*" * 80)
                    print(igibson.__logo__)
                    print("*" * 80)
                    print("*" * 80)
                    signal.alarm(TIMEOUT)
                    s = timed_input(examples_list[idx])
                    # disable the alarm after success
                    signal.alarm(0)
                    if s:
                        continue
                    print("Executing " + examples_list[idx])

                    i = importlib.import_module("igibson.examples." + examples_list[idx])
                    if test_mode == "random":
                        p = Process(
                            target=i.main,
                            args=(
                                'selection="random"',
                                "headless=True",
                                "short_exec=True",
                            ),
                        )
                    else:
                        p = Process(
                            target=i.main,
                            args=(
                                'selection="user"',
                                "headless=False",
                                "short_exec=False",
                            ),
                        )

                    p.start()
                    p.join()
                    print("Ended " + examples_list[idx])
                else:
                    print(
                        "The web UI demos to create new activity definitions require additional terminal commands. "
                        "Skipping them."
                    )
        elif selected_demo == 2:
            print("Exit")
            return
        elif selected_demo == 3:
            test_mode = ["user", "random"][test_mode == "user"]
            print("Test mode now " + ["OFF", "ON"][test_mode == "random"])
            examples_list[3] = ["switch to test mode", "switch to interactive mode"][test_mode == "random"]
        else:  # running a selected example
            if any(excluded_example in examples_list[selected_demo] for excluded_example in excluded_examples):
                print(
                    "You have selected an example that requires additional terminal commands or packages "
                    "(e.g. VR, web UI). Please, follow the instructions in the README of that example."
                )
                sys.exit(0)
            print(
                "Executing "
                + examples_list[selected_demo]
                + " "
                + ["in interactive mode", "in test mode"][test_mode == "random"]
            )
            i = importlib.import_module("igibson.examples." + examples_list[selected_demo])
            i.main(selection=test_mode, headless=test_mode, short_exec=test_mode)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
