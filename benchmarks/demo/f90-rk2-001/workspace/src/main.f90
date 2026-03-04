program rk2_cli
   use flap, only: command_line_interface
   use rk2_solver
   implicit none

   type(command_line_interface) :: cli
   integer :: error
   character(len=64) :: rhs_name
   real(8) :: y0, t0, h
   integer :: n_steps, i
   real(8), allocatable :: y(:)

   call cli%init(progname='rk2_cli', description='RK2 midpoint solver CLI')
   call cli%add(positional=.true., position=1, help='rhs_name', required=.true., act='store', error=error)
   if (error /= 0) stop 2
   call cli%add(positional=.true., position=2, help='y0', required=.true., act='store', error=error)
   if (error /= 0) stop 2
   call cli%add(positional=.true., position=3, help='t0', required=.true., act='store', error=error)
   if (error /= 0) stop 2
   call cli%add(positional=.true., position=4, help='h', required=.true., act='store', error=error)
   if (error /= 0) stop 2
   call cli%add(positional=.true., position=5, help='n_steps', required=.true., act='store', error=error)
   if (error /= 0) stop 2

   call cli%parse(error=error)
   if (error /= 0) stop 2

   call cli%get(position=1, val=rhs_name, error=error)
   if (error /= 0) stop 2
   call cli%get(position=2, val=y0, error=error)
   if (error /= 0) stop 2
   call cli%get(position=3, val=t0, error=error)
   if (error /= 0) stop 2
   call cli%get(position=4, val=h, error=error)
   if (error /= 0) stop 2
   call cli%get(position=5, val=n_steps, error=error)
   if (error /= 0) stop 2

   if (n_steps < 0) then
      stop 2
   end if

   allocate (y(0:n_steps))
   if (trim(rhs_name) == "exp_growth") then
      call solve_rk2_midpoint(exp_growth_rhs, y0, t0, h, n_steps, y)
   else if (trim(rhs_name) == "damped_forced") then
      call solve_rk2_midpoint(damped_forced_rhs, y0, t0, h, n_steps, y)
   else
      stop 2
   end if

   do i = 0, n_steps
      write (*, '(F0.15)') y(i)
   end do
end program rk2_cli
