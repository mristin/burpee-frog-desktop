"""Jump burpees and lead the frog to its beloved one."""

import argparse
import fractions
import importlib.resources
import os.path
import pathlib
import random
import sys
import time
from typing import Optional, Final, List, MutableMapping, Union, Tuple

import pygame
import pygame.freetype
from icontract import require

import burpeefrog
import burpeefrog.events
from burpeefrog.common import assert_never

assert burpeefrog.__doc__ == __doc__

PACKAGE_DIR = (
    pathlib.Path(str(importlib.resources.files(__package__)))
    if __package__ is not None
    else pathlib.Path(os.path.realpath(__file__)).parent
)


class Media:
    """Represent all the media loaded in the main memory from the file system."""

    def __init__(
        self,
        background: pygame.surface.Surface,
        frog_sprites: List[pygame.surface.Surface],
        vehicle_sprites: List[pygame.surface.Surface],
        trunk_sprites: List[pygame.surface.Surface],
        heart_sprite: pygame.surface.Surface,
        font: pygame.freetype.Font,  # type: ignore
        jump_sound: pygame.mixer.Sound,
        squash_sound: pygame.mixer.Sound,
        drowning_sound: pygame.mixer.Sound,
        happy_end_sound: pygame.mixer.Sound,
    ) -> None:
        """Initialize with the given values."""
        self.background = background
        self.frog_sprites = frog_sprites
        self.vehicle_sprites = vehicle_sprites
        self.trunk_sprites = trunk_sprites
        self.heart_sprite = heart_sprite
        self.font = font
        self.jump_sound = jump_sound
        self.squash_sound = squash_sound
        self.drowning_sound = drowning_sound
        self.happy_end_sound = happy_end_sound


SCENE_WIDTH = 448
SCENE_HEIGHT = 510
LANE_HEIGHT = SCENE_HEIGHT // 13

#: Velocity of the vehicles in the lanes, in pixels / second
VEHICLE_VELOCITY = 0.06

#: Velocity of the trunks in the river, in pixels / second
TRUNK_VELOCITY = 0.06
TRUNK_WIDTH = 200

FROG_WIDTH = 25
FROG_HEIGHT = 35

#: Start position of the frog
FROG_START_XY = (
    SCENE_WIDTH / 2 - FROG_WIDTH / 2,
    SCENE_HEIGHT - LANE_HEIGHT + (LANE_HEIGHT - FROG_HEIGHT) / 2,
)

#: Jump length in pixels
JUMP_DISTANCE = LANE_HEIGHT

#: Jump duration in seconds
JUMP_DURATION = 0.25


def load_media() -> Media:
    """Load the media from the file system."""
    background = pygame.image.load(
        str(PACKAGE_DIR / "media/images/background.png")
    ).convert_alpha()

    assert isinstance(background, pygame.surface.Surface)
    assert (
        background.get_width() == SCENE_WIDTH
    ), f"{background.get_width()=}, {SCENE_WIDTH=}"
    assert (
        background.get_height() == SCENE_HEIGHT
    ), f"{background.get_height()=}, {SCENE_HEIGHT=}"

    return Media(
        background=background,
        frog_sprites=[
            pygame.transform.scale(
                pygame.image.load(
                    str(PACKAGE_DIR / f"media/images/frog{i}.png")
                ).convert_alpha(),
                (FROG_WIDTH, FROG_HEIGHT),
            )
            for i in range(5)
        ],
        vehicle_sprites=[
            pygame.image.load(
                str(PACKAGE_DIR / f"media/images/vehicle{i}.png")
            ).convert_alpha()
            for i in range(5)
        ],
        trunk_sprites=[
            pygame.transform.scale(
                pygame.image.load(
                    str(PACKAGE_DIR / f"media/images/trunk{i}.png")
                ).convert_alpha(),
                (TRUNK_WIDTH, 33),
            )
            for i in range(1)
        ],
        heart_sprite=pygame.image.load(
            str(PACKAGE_DIR / "media/images/heart.png")
        ).convert_alpha(),
        font=pygame.freetype.Font(str(PACKAGE_DIR / "media/fonts/freesansbold.ttf")),  # type: ignore
        jump_sound=pygame.mixer.Sound(str(PACKAGE_DIR / "media/sfx/jump.ogg")),
        squash_sound=pygame.mixer.Sound(str(PACKAGE_DIR / "media/sfx/squash.ogg")),
        drowning_sound=pygame.mixer.Sound(str(PACKAGE_DIR / "media/sfx/drowning.ogg")),
        happy_end_sound=pygame.mixer.Sound(
            str(PACKAGE_DIR / "media/sfx/happy_end.ogg")
        ),
    )


class Vehicle:
    """Model a vehicle on the vehicle lane."""

    sprite: Final[pygame.surface.Surface]

    #: Position relative to the screen
    #:
    #: The position can be negative if the vehicle is partially visible
    xy: Tuple[float, float]

    #: Velocity of the vehicle in pixels per second.
    #:
    #: ``< 0`` means going left, ``>= 0`` means going right.
    velocity: Final[float]

    def __init__(
        self, sprite: pygame.surface.Surface, xy: Tuple[float, float], velocity: float
    ) -> None:
        """Initialize with the given values."""
        self.sprite = sprite
        self.xy = xy
        self.velocity = velocity


class Trunk:
    """Model a trunk floating in the river."""

    sprite: Final[pygame.surface.Surface]

    #: Position relative to the screen
    #:
    #: The position can be negative if the vehicle is partially visible
    xy: Tuple[float, float]

    #: Velocity of the trunk in pixels per second.
    #:
    #: ``< 0`` means going left, ``>= 0`` means going right.
    velocity: Final[float]

    def __init__(
        self, sprite: pygame.surface.Surface, xy: Tuple[float, float], velocity: float
    ) -> None:
        """Initialize with the given values."""
        self.sprite = sprite
        self.xy = xy
        self.velocity = velocity


class MeadowLane:
    """Model a lane where there is no danger."""


class VehicleLane:
    """Model a lane where vehicles pass."""

    vehicles: Final[List[Vehicle]]

    def __init__(self) -> None:
        """Initialize empty."""
        self.vehicles = []


class TrunkLane:
    """Model a lane where trunks float."""

    trunks: Final[List[Trunk]]

    def __init__(self) -> None:
        """Initialize empty."""
        self.trunks = []


Lane = Union[MeadowLane, VehicleLane, TrunkLane]


class Jump:
    """Model a jump of the frog up."""

    #: The position where the frog jumped from, relative to the screen
    origin_xy: Tuple[float, float]

    #: Target position of the jump relative to the screen
    target_xy: Tuple[float, float]

    #: Seconds since epoch
    start: float

    #: Seconds since epoch
    eta: float

    def __init__(
        self,
        origin_xy: Tuple[float, float],
        target_xy: Tuple[float, float],
        start: float,
        eta: float,
    ) -> None:
        """Initialize with the given values."""
        self.origin_xy = origin_xy
        self.target_xy = target_xy
        self.start = start
        self.eta = eta


class Frog:
    """Model the frog state."""

    xy: Tuple[float, float]

    jump: Optional[Jump]

    def __init__(self, xy: Tuple[float, float], jump: Optional[Jump]) -> None:
        """Initialize with the given values."""
        self.xy = xy
        self.jump = jump


class State:
    """Capture the global state of the game."""

    #: Set if we received the signal to quit the game
    received_quit: bool

    #: Timestamp when the game started, seconds since epoch
    game_start: float

    #: Current clock in the game, seconds since epoch
    now: float

    #: Set when the game finishes
    game_over: Optional[burpeefrog.events.GameOverKind]

    #: Map of the buttons to timestamps when they were pressed down
    jump_buttons: MutableMapping[burpeefrog.events.Button, float]

    #: Set if the frog is instructed to jump at the next tick
    jump_pending: bool

    #: State of the lanes
    lanes: List[Lane]

    #: State of the frog
    frog: Frog

    def __init__(self, game_start: float) -> None:
        """Initialize with the given values and the defaults."""
        initialize_state(self, game_start)


def initialize_state(state: State, game_start: float) -> None:
    """Initialize the state to the start one."""
    state.received_quit = False
    state.game_start = game_start
    state.now = game_start
    state.game_over = None

    state.lanes = [
        MeadowLane(),
        VehicleLane(),
        VehicleLane(),
        VehicleLane(),
        VehicleLane(),
        VehicleLane(),
        MeadowLane(),
        TrunkLane(),
        TrunkLane(),
        TrunkLane(),
        TrunkLane(),
        TrunkLane(),
        MeadowLane(),
    ]

    state.frog = Frog(xy=FROG_START_XY, jump=None)

    state.jump_buttons = dict()
    state.jump_pending = False


#: Buttons that need to be pressed down to initiate a jump
JUMP_BUTTONS = {
    burpeefrog.events.Button.CROSS,
    burpeefrog.events.Button.CIRCLE,
    burpeefrog.events.Button.SQUARE,
    burpeefrog.events.Button.TRIANGLE,
}

#: Time delta within which all jump buttons must be pressed down.
#:
#: Note that we can not expect the player to press all the buttons at the same time,
#: but some time difference between, say, pressing the front and the back rows is
#: expected.
#:
#: In seconds.
TIME_TOLERANCE_OF_JUMP_BUTTONS = 1.25


def update_vehicles(state: State, media: Media) -> None:
    """Move vehicles, spawn new ones and remove those that left."""
    for lane_i, lane in enumerate(state.lanes):
        if isinstance(lane, VehicleLane):
            # Move
            for vehicle in lane.vehicles:
                vehicle.xy = (vehicle.xy[0] + vehicle.velocity, vehicle.xy[1])

            # Spawn and remove
            spawn = False

            updated_vehicles = []

            if len(lane.vehicles) == 0:
                spawn = True
            else:
                for vehicle in lane.vehicles:
                    if vehicle.velocity >= 0 and vehicle.xy[0] >= SCENE_WIDTH:
                        spawn = True
                    elif (
                        vehicle.velocity < 0
                        and vehicle.xy[0] + vehicle.sprite.get_width() < 0
                    ):
                        spawn = True
                    else:
                        updated_vehicles.append(vehicle)

            if spawn:
                direction = 1 if lane_i % 2 == 0 else -1
                velocity = direction * VEHICLE_VELOCITY
                sprite = random.choice(media.vehicle_sprites)

                vehicle_y = (
                    SCENE_HEIGHT
                    - ((lane_i + 1) * LANE_HEIGHT)
                    + (LANE_HEIGHT - sprite.get_height()) // 2
                )

                if velocity >= 0:
                    xy = (
                        -sprite.get_width() - random.random() * sprite.get_width(),
                        vehicle_y,
                    )
                    updated_vehicles.insert(
                        0, Vehicle(sprite=sprite, xy=xy, velocity=velocity)
                    )
                else:
                    xy = (SCENE_WIDTH + random.random() * sprite.get_width(), vehicle_y)
                    updated_vehicles.append(
                        Vehicle(sprite=sprite, xy=xy, velocity=velocity)
                    )

                lane.vehicles[:] = updated_vehicles


@require(lambda xmin_a, xmax_a: xmin_a <= xmax_a)
@require(lambda ymin_a, ymax_a: ymin_a <= ymax_a)
@require(lambda xmin_b, xmax_b: xmin_b <= xmax_b)
@require(lambda ymin_b, ymax_b: ymin_b <= ymax_b)
def intersect(
    xmin_a: Union[int, float],
    ymin_a: Union[int, float],
    xmax_a: Union[int, float],
    ymax_a: Union[int, float],
    xmin_b: Union[int, float],
    ymin_b: Union[int, float],
    xmax_b: Union[int, float],
    ymax_b: Union[int, float],
) -> bool:
    """Return true if the two bounding boxes intersect."""
    return (xmin_a <= xmax_b and xmax_a >= xmin_b) and (
        ymin_a <= ymax_b and ymax_a >= ymin_b
    )


def lane_index_for_y(state: State, y: float) -> int:
    """Compute the lane index given the position."""
    return int(SCENE_HEIGHT - y) // LANE_HEIGHT


def find_trunk_on_which_frog(state: State) -> Optional[Trunk]:
    """Find the trunk on which the frog is sailing, if it is sailing on one."""
    if state.frog.jump is not None:
        return None

    frog_lane_i = lane_index_for_y(state=state, y=state.frog.xy[1])

    frog_lane = state.lanes[frog_lane_i]
    if isinstance(frog_lane, TrunkLane):
        for trunk in frog_lane.trunks:
            # If the frog is on the trunk, sail it along
            if (
                trunk.xy[0] <= state.frog.xy[0]
                and state.frog.xy[0] + FROG_WIDTH
                < trunk.xy[0] + trunk.sprite.get_width()
            ):
                return trunk

    return None


def update_trunks_and_sail_frog(state: State, media: Media) -> None:
    """
    Move trunks, spawn new ones and remove those that left.

    If frog is on a trunk, it sails along.
    """
    # If the frog is on the trunk, sail it along
    trunk_on_which_frog = find_trunk_on_which_frog(state)
    if trunk_on_which_frog is not None:
        state.frog.xy = (
            state.frog.xy[0] + trunk_on_which_frog.velocity,
            state.frog.xy[1],
        )

    for lane_i, lane in enumerate(state.lanes):
        if isinstance(lane, TrunkLane):
            # Move
            for trunk in lane.trunks:
                trunk.xy = (trunk.xy[0] + trunk.velocity, trunk.xy[1])

            # Spawn and remove
            spawn = False

            updated_trunks = []

            if len(lane.trunks) == 0:
                spawn = True
            else:
                for trunk in lane.trunks:
                    if trunk.velocity >= 0 and trunk.xy[0] >= SCENE_WIDTH:
                        spawn = True
                    elif (
                        trunk.velocity < 0
                        and trunk.xy[0] + trunk.sprite.get_width() < 0
                    ):
                        spawn = True
                    else:
                        updated_trunks.append(trunk)

            if spawn:
                direction = 1 if lane_i % 2 == 0 else -1
                velocity = direction * TRUNK_VELOCITY
                sprite = random.choice(media.trunk_sprites)

                trunk_y = (
                    SCENE_HEIGHT
                    - ((lane_i + 1) * LANE_HEIGHT)
                    + (LANE_HEIGHT - sprite.get_height()) // 2
                )

                if velocity >= 0:
                    xy = (-sprite.get_width() - random.random() * 20, trunk_y)
                    updated_trunks.insert(
                        0, Trunk(sprite=sprite, xy=xy, velocity=velocity)
                    )
                else:
                    xy = (SCENE_WIDTH + random.random() * 20, trunk_y)
                    updated_trunks.append(
                        Trunk(sprite=sprite, xy=xy, velocity=velocity)
                    )

            lane.trunks[:] = updated_trunks


def handle_in_game(
    state: State, our_event_queue: List[burpeefrog.events.EventUnion], media: Media
) -> None:
    """Consume the first action in the queue during the game."""
    if len(our_event_queue) == 0:
        return

    event = our_event_queue.pop(0)

    now = time.time()

    if isinstance(event, burpeefrog.events.ButtonDown):
        if event.button not in JUMP_BUTTONS:
            return

        state.jump_buttons[event.button] = now

        # Check if we received the signal to jump the frog.
        if len(state.jump_buttons) > 0 and len(
            state.jump_buttons.keys() & JUMP_BUTTONS
        ) == len(JUMP_BUTTONS):
            min_timestamp = min(state.jump_buttons.values())
            max_timestamp = max(state.jump_buttons.values())

            timestamp_delta = max_timestamp - min_timestamp

            if timestamp_delta < TIME_TOLERANCE_OF_JUMP_BUTTONS:
                our_event_queue.append(burpeefrog.events.ReceivedJump())
                state.jump_buttons.clear()

    elif isinstance(event, burpeefrog.events.ReceivedJump):
        state.jump_pending = True

    elif isinstance(event, burpeefrog.events.Tick):
        state.now = now

        frog_lane_index = lane_index_for_y(state, y=state.frog.xy[1])
        if frog_lane_index == len(state.lanes) - 1:
            our_event_queue.append(
                burpeefrog.events.GameOver(
                    kind=burpeefrog.events.GameOverKind.HAPPY_END
                )
            )
            return

        if state.jump_pending:
            if state.frog.jump is None:
                state.frog.jump = Jump(
                    origin_xy=state.frog.xy,
                    target_xy=(state.frog.xy[0], state.frog.xy[1] - JUMP_DISTANCE),
                    start=now,
                    eta=now + JUMP_DURATION,
                )

            state.jump_pending = False

        # Jump the frog
        if state.frog.jump is not None:
            if now >= state.frog.jump.eta:
                state.frog.xy = state.frog.jump.target_xy
                state.frog.jump = None
            else:
                pixels_jumped = (
                    (now - state.frog.jump.start)
                    / (state.frog.jump.eta - state.frog.jump.start)
                ) * JUMP_DISTANCE

                state.frog.xy = (
                    state.frog.jump.origin_xy[0],
                    state.frog.jump.origin_xy[1] - pixels_jumped,
                )

        update_vehicles(state, media)

        # Check the collision between the frog and the car
        frog_lane_index = lane_index_for_y(state, y=state.frog.xy[1])
        frog_lane = state.lanes[frog_lane_index]

        if isinstance(frog_lane, VehicleLane):
            for vehicle in frog_lane.vehicles:
                if intersect(
                    vehicle.xy[0],
                    vehicle.xy[1],
                    vehicle.xy[0] + vehicle.sprite.get_width() - 1,
                    vehicle.xy[1] + vehicle.sprite.get_height() - 1,
                    state.frog.xy[0],
                    state.frog.xy[1],
                    state.frog.xy[0] + FROG_WIDTH - 1,
                    state.frog.xy[1] + FROG_HEIGHT - 1,
                ):
                    our_event_queue.append(
                        burpeefrog.events.GameOver(
                            kind=burpeefrog.events.GameOverKind.CRASH
                        )
                    )

        update_trunks_and_sail_frog(state, media)

        # Check if the frog drowned
        if (
            state.frog.jump is None
            and isinstance(frog_lane, TrunkLane)
            and find_trunk_on_which_frog(state) is None
        ):
            our_event_queue.append(
                burpeefrog.events.GameOver(kind=burpeefrog.events.GameOverKind.DROWNING)
            )

        # Check if the frog left the scene, and consequently drowned
        if state.frog.xy[0] >= SCENE_WIDTH or state.frog.xy[0] + FROG_WIDTH < 0:
            our_event_queue.append(
                burpeefrog.events.GameOver(kind=burpeefrog.events.GameOverKind.DROWNING)
            )

    else:
        # Ignore the event
        pass


def handle(
    state: State, our_event_queue: List[burpeefrog.events.EventUnion], media: Media
) -> None:
    """Consume the first action in the queue."""
    if len(our_event_queue) == 0:
        return

    if isinstance(our_event_queue[0], burpeefrog.events.ReceivedQuit):
        our_event_queue.pop(0)
        state.received_quit = True

    elif isinstance(our_event_queue[0], burpeefrog.events.ReceivedRestart):
        our_event_queue.pop(0)
        initialize_state(state, game_start=time.time())

    elif isinstance(our_event_queue[0], burpeefrog.events.GameOver):
        event = our_event_queue[0]
        our_event_queue.pop(0)

        if state.game_over is None:
            state.game_over = event.kind
            if state.game_over is burpeefrog.events.GameOverKind.HAPPY_END:
                media.happy_end_sound.play()
            elif state.game_over is burpeefrog.events.GameOverKind.CRASH:
                media.squash_sound.play()
            elif state.game_over is burpeefrog.events.GameOverKind.DROWNING:
                media.drowning_sound.play()
            else:
                assert_never(state.game_over)
    else:
        handle_in_game(state, our_event_queue, media)


def render_game_over(state: State, media: Media) -> pygame.surface.Surface:
    """Render the "game over" dialogue as a scene."""
    scene = pygame.surface.Surface((SCENE_WIDTH, SCENE_HEIGHT))
    scene.fill((0, 0, 0))

    assert state.game_over is not None

    if state.game_over is burpeefrog.events.GameOverKind.HAPPY_END:
        big_heart = pygame.transform.scale(media.heart_sprite, (128, 128))
        scene.blit(big_heart, (SCENE_WIDTH // 2 - big_heart.get_width(), 50))
    elif (
        state.game_over is burpeefrog.events.GameOverKind.CRASH
        or state.game_over is burpeefrog.events.GameOverKind.DROWNING
    ):
        media.font.render_to(scene, (20, 20), "Game Over :'(", (255, 255, 255), size=16)
    else:
        assert_never(state.game_over)

    media.font.render_to(
        scene,
        (20, 490),
        'Press "q" to quit and "r" to restart',
        (255, 255, 255),
        size=16,
    )

    return scene


def render_quit(media: Media) -> pygame.surface.Surface:
    """Render the "Quitting..." dialogue as a scene."""
    scene = pygame.surface.Surface((SCENE_WIDTH, SCENE_HEIGHT))
    scene.fill((0, 0, 0))

    media.font.render_to(scene, (20, 20), "Quitting...", (255, 255, 255), size=32)

    return scene


def render_game(state: State, media: Media) -> pygame.surface.Surface:
    """Render the game scene."""
    scene = media.background.copy()

    media.font.render_to(
        scene, (10, 490), 'Press "q" to quit and "r" to restart', (0, 0, 0), size=12
    )

    for lane in state.lanes:
        if isinstance(lane, VehicleLane):
            for vehicle in lane.vehicles:
                if vehicle.velocity < 0:
                    vehicle_sprite = pygame.transform.flip(vehicle.sprite, True, False)
                else:
                    vehicle_sprite = vehicle.sprite

                scene.blit(vehicle_sprite, vehicle.xy)
        elif isinstance(lane, TrunkLane):
            for trunk in lane.trunks:
                scene.blit(trunk.sprite, trunk.xy)

    if state.frog.jump is None:
        scene.blit(media.frog_sprites[0], state.frog.xy)
    else:
        frog_sprite_i = int(
            (state.now - state.frog.jump.start)
            / (state.frog.jump.eta - state.frog.jump.start)
            * len(media.frog_sprites)
        )
        frog_sprite_i = max(0, min(frog_sprite_i, len(media.frog_sprites) - 1))

        scene.blit(media.frog_sprites[frog_sprite_i], state.frog.xy)

    return scene


def render(state: State, media: Media) -> pygame.surface.Surface:
    """Render the state of the program."""
    if state.received_quit:
        return render_quit(media)

    if state.game_over is not None:
        return render_game_over(state, media)

    return render_game(state, media)


def resize_scene_to_surface_and_blit(
    scene: pygame.surface.Surface, surface: pygame.surface.Surface
) -> None:
    """Draw the scene on surface resizing it to maximum at constant aspect ratio."""
    surface.fill((0, 0, 0))

    surface_aspect_ratio = fractions.Fraction(surface.get_width(), surface.get_height())
    scene_aspect_ratio = fractions.Fraction(scene.get_width(), scene.get_height())

    if scene_aspect_ratio < surface_aspect_ratio:
        new_scene_height = surface.get_height()
        new_scene_width = scene.get_width() * (new_scene_height / scene.get_height())

        scene = pygame.transform.scale(scene, (new_scene_width, new_scene_height))

        margin = int((surface.get_width() - scene.get_width()) / 2)

        surface.blit(scene, (margin, 0))

    elif scene_aspect_ratio == surface_aspect_ratio:
        new_scene_width = surface.get_width()
        new_scene_height = scene.get_height()

        scene = pygame.transform.scale(scene, (new_scene_width, new_scene_height))

        surface.blit(scene, (0, 0))
    else:
        new_scene_width = surface.get_width()
        new_scene_height = int(
            scene.get_height() * (new_scene_width / scene.get_width())
        )

        scene = pygame.transform.scale(scene, (new_scene_width, new_scene_height))

        margin = int((surface.get_height() - scene.get_height()) / 2)

        surface.blit(scene, (0, margin))


def main(prog: str) -> int:
    """
    Execute the main routine.

    :param prog: name of the program to be displayed in the help
    :return: exit code
    """
    pygame.joystick.init()
    joysticks = [
        pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())
    ]

    parser = argparse.ArgumentParser(prog=prog, description=__doc__)
    parser.add_argument(
        "--version", help="show the current version and exit", action="store_true"
    )

    parser.add_argument(
        "--list_joysticks", help="List joystick GUIDs and exit", action="store_true"
    )
    if len(joysticks) >= 1:
        parser.add_argument(
            "--joystick",
            help="Joystick to use for the game",
            choices=[joystick.get_guid() for joystick in joysticks],
            default=joysticks[0].get_guid(),
        )

    # NOTE (mristin, 2022-12-16):
    # The module ``argparse`` is not flexible enough to understand special options such
    # as ``--version`` so we manually hard-wire.
    if "--version" in sys.argv and "--help" not in sys.argv:
        print(burpeefrog.__version__)
        return 0

    if "--list_joysticks" in sys.argv and "--help" not in sys.argv:
        for joystick in joysticks:
            print(f"Joystick {joystick.get_name()}, GUID: {joystick.get_guid()}")
        return 0

    args = parser.parse_args()

    # noinspection PyUnusedLocal
    active_joystick = None  # type: Optional[pygame.joystick.Joystick]
    if len(joysticks) == 0:
        print(
            f"There are no joysticks plugged in. "
            f"{prog.capitalize()} requires a joystick.",
            file=sys.stderr,
        )
        return 1

    else:
        active_joystick = next(
            joystick for joystick in joysticks if joystick.get_guid() == args.joystick
        )

    assert active_joystick is not None
    print(
        f"Using the joystick: {active_joystick.get_name()} {active_joystick.get_guid()}"
    )

    # NOTE (mristin, 2023-01-01):
    # We have to think a bit better about how to deal with keyboard and joystick input.
    # For rapid development, we simply map the buttons of our concrete dance mat to
    # button numbers.
    button_map = {
        6: burpeefrog.events.Button.CROSS,
        2: burpeefrog.events.Button.UP,
        7: burpeefrog.events.Button.CIRCLE,
        3: burpeefrog.events.Button.RIGHT,
        5: burpeefrog.events.Button.SQUARE,
        1: burpeefrog.events.Button.DOWN,
        4: burpeefrog.events.Button.TRIANGLE,
        0: burpeefrog.events.Button.LEFT,
    }

    pygame.init()
    pygame.mixer.pre_init()
    pygame.mixer.init()

    pygame.display.set_caption("Burpee-frog")
    surface = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)

    try:
        media = load_media()
    except Exception as exception:
        print(
            f"Failed to load the media: {exception.__class__.__name__} {exception}",
            file=sys.stderr,
        )
        return 1

    now = time.time()

    state = State(game_start=now)

    our_event_queue = []  # type: List[burpeefrog.events.EventUnion]

    # Reuse the tick object so that we don't have to create it every time
    tick_event = burpeefrog.events.Tick()

    try:
        while not state.received_quit:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    our_event_queue.append(burpeefrog.events.ReceivedQuit())

                elif (
                    event.type == pygame.JOYBUTTONDOWN
                    and joysticks[event.instance_id] is active_joystick
                ):
                    # NOTE (mristin, 2022-01-01):
                    # Map joystick buttons to our canonical buttons;
                    # This is necessary if we ever want to support other dance mats.
                    our_button = button_map.get(event.button, None)
                    if our_button is not None:
                        our_event_queue.append(burpeefrog.events.ButtonDown(our_button))

                elif event.type == pygame.KEYDOWN and event.key in (
                    pygame.K_ESCAPE,
                    pygame.K_q,
                ):
                    our_event_queue.append(burpeefrog.events.ReceivedQuit())

                elif event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    # NOTE (mristin, 2022-01-01):
                    # Restart the game whenever "r" is pressed
                    our_event_queue.append(burpeefrog.events.ReceivedRestart())

                elif event.type == pygame.KEYDOWN and event.key == pygame.K_j:
                    our_event_queue.append(burpeefrog.events.ReceivedJump())

                else:
                    # Ignore the event that we do not handle
                    pass

            our_event_queue.append(tick_event)

            while len(our_event_queue) > 0:
                handle(state, our_event_queue, media)

            scene = render(state, media)
            resize_scene_to_surface_and_blit(scene, surface)
            pygame.display.flip()
    finally:
        print("Quitting the game...")
        tic = time.time()
        pygame.joystick.quit()
        pygame.quit()
        print(f"Quit the game after: {time.time() - tic:.2f} seconds")

    return 0


def entry_point() -> int:
    """Provide an entry point for a console script."""
    return main(prog="burpee-frog")


if __name__ == "__main__":
    sys.exit(main(prog="burpee-frog"))
