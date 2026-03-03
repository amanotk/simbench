program rk2_cli
  use rk2_solver
  implicit none

  character(len=64) :: rhs_name
  character(len=64) :: arg
  real(8) :: y0, t0, h
  integer :: n_steps, i
  real(8), allocatable :: y(:)

  if (command_argument_count() /= 5) then
    write(*, '(A)') "usage: rk2_cli <rhs_name> <y0> <t0> <h> <n_steps>"
    stop 2
  end if

  call get_command_argument(1, rhs_name)

  call get_command_argument(2, arg)
  read(arg, *) y0

  call get_command_argument(3, arg)
  read(arg, *) t0

  call get_command_argument(4, arg)
  read(arg, *) h

  call get_command_argument(5, arg)
  read(arg, *) n_steps

  if (n_steps < 0) then
    stop 2
  end if

  allocate(y(0:n_steps))
  if (trim(rhs_name) == "exp_growth") then
    call solve_rk2_midpoint(exp_growth_rhs, y0, t0, h, n_steps, y)
  else if (trim(rhs_name) == "damped_forced") then
    call solve_rk2_midpoint(damped_forced_rhs, y0, t0, h, n_steps, y)
  else
    stop 2
  end if

  do i = 0, n_steps
    write(*, '(F0.15)') y(i)
  end do
end program rk2_cli
