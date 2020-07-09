"""A simple, 2D peridynamics simulation example."""
import argparse
import cProfile
from io import StringIO
import numpy as np
import pathlib
from peridynamics import Model, ModelCL, ModelCLBen
from peridynamics.model import initial_crack_helper
from peridynamics.integrators import Euler
from pstats import SortKey, Stats

mesh_file = pathlib.Path(__file__).parent.absolute() / "test.vtk"


@initial_crack_helper
def is_crack(x, y):
    """Determine whether a pair of particles define the crack."""
    output = 0
    crack_length = 0.3
    p1 = x
    p2 = y
    if x[0] > y[0]:
        p2 = x
        p1 = y
    # 1e-6 makes it fall one side of central line of particles
    if p1[0] < 0.5 + 1e-6 and p2[0] > 0.5 + 1e-6:
        # draw a straight line between them
        m = (p2[1] - p1[1]) / (p2[0] - p1[0])
        c = p1[1] - m * p1[0]
        # height a x = 0.5
        height = m * 0.5 + c
        if (height > 0.5 * (1 - crack_length)
                and height < 0.5 * (1 + crack_length)):
            output = 1
    return output


def is_tip(horizon, x):
    """Return if the particle coordinate is a `tip`."""
    output = 0
    if x[0] > 1.0 - 1. * horizon:
        output = 1
    return output


def is_boundary(horizon, x):
    """
    Return if the particle coordinate is a displacement boundary.

    Function which marks displacement boundary constrained particles
    2 is no boundary condition (the number here is an arbitrary choice)
    -1 is displacement loaded IN -ve direction
    1 is displacement loaded IN +ve direction
    0 is clamped boundary
    """
    # Does not live on a boundary
    bnd = 2
    # Does live on boundary
    if x[0] < 1.5 * horizon:
        bnd = -1
    elif x[0] > 1.0 - 1.5 * horizon:
        bnd = 1
    return bnd


def is_forces_boundary(horizon, x):
    """
    Return if the particle coordinate is a force boundary.

    Marks types of body force on the particles
    2 is no boundary condition (the number here is an arbitrary choice)
    -1 is force loaded IN -ve direction
    1 is force loaded IN +ve direction
    """
    bnd = [2, 2, 2]
    return bnd


def boundary_function(model, u, step):
    """
    Apply a load to the system.

    Particles on each of the sides of the system are pulled apart with
    increasing time step.
    """
    load_rate = 0.000005

    u[model.lhs, 1:3] = 0.
    u[model.rhs, 1:3] = 0.

    extension = 0.5 * step * load_rate
    u[model.lhs, 0] = -extension
    u[model.rhs, 0] = extension

    return u


def main():
    """Conduct a peridynamics simulation."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', action='store_const', const=True)
    parser.add_argument('--opencl', action='store_const', const=True)
    parser.add_argument('--ben', action='store_const', const=True)
    args = parser.parse_args()
    if args.profile:
        profile = cProfile.Profile()
        profile.enable()

    if args.opencl:
        if args.ben:
            model = ModelCLBen(
                mesh_file, horizon=0.1, critical_stretch=[0.005],
                bond_stiffness=[18.00 * 0.05 / (np.pi * 0.1**4)],
                dimensions=2, density=2.0, initial_crack=is_crack, dt=1e-3)
        else:
            model = ModelCL(mesh_file, horizon=0.1, critical_stretch=0.005,
                            bond_stiffness=18.0 * 0.05 / (np.pi * 0.1**4),
                            initial_crack=is_crack)
    else:
        model = Model(mesh_file, horizon=0.1, critical_stretch=0.005,
                      bond_stiffness=18.0 * 0.05 / (np.pi * 0.1**4),
                      initial_crack=is_crack)

    # Set left-hand side and right-hand side of boundary
    model.lhs = np.nonzero(model.coords[:, 0] < 1.5*model.horizon)
    model.rhs = np.nonzero(model.coords[:, 0] > 1.0 - 1.5*model.horizon)

    if (args.opencl and args.ben):
        u, damage, *_ = model.simulate(
            steps=1000, is_boundary=is_boundary,
            is_forces_boundary=is_forces_boundary, is_tip=is_tip,
            displacement_rate=0.000005/2, write=50)
    else:

        integrator = Euler(dt=1e-3)

        u, damage, *_ = model.simulate(
            steps=1000,
            integrator=integrator,
            boundary_function=boundary_function,
            write=50
            )

    if args.profile:
        profile.disable()
        s = StringIO()
        stats = Stats(profile, stream=s).sort_stats(SortKey.CUMULATIVE)
        stats.print_stats(.05)
        print(s.getvalue())


if __name__ == "__main__":
    main()
